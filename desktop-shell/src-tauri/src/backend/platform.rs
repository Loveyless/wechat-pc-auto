use std::{
    env,
    fs::{self, OpenOptions},
    io::{ErrorKind, Write},
    path::PathBuf,
    process::Command,
    thread,
    time::{Duration, Instant},
};

use serde::{Deserialize, Serialize};

const LOCK_WAIT_INTERVAL_MS: u64 = 100;
const PROCESS_EXIT_TIMEOUT_MS: u64 = 3_000;
const PROCESS_FORCE_KILL_TIMEOUT_MS: u64 = 2_000;

#[derive(Deserialize, Serialize)]
struct LockOwner {
    pid: u32,
    #[serde(default)]
    start_token: String,
}

pub struct BackendBootstrapLock {
    path: PathBuf,
    owner: LockOwner,
}

impl Drop for BackendBootstrapLock {
    fn drop(&mut self) {
        let current_owner = read_lock_owner(&self.path);
        if current_owner
            .as_ref()
            .map(|owner| {
                owner.pid == self.owner.pid && owner.start_token == self.owner.start_token
            })
            .unwrap_or(false)
        {
            let _ = fs::remove_file(&self.path);
        }
    }
}

pub fn acquire_bootstrap_lock(
    lock_name: &str,
    timeout_ms: u32,
) -> Result<BackendBootstrapLock, String> {
    let lock_path = lock_path_for_name(lock_name)?;
    let owner = LockOwner {
        pid: std::process::id(),
        start_token: process_start_token(std::process::id()).unwrap_or_default(),
    };
    let deadline = Instant::now() + Duration::from_millis(u64::from(timeout_ms));

    loop {
        match try_create_lock(&lock_path, &owner) {
            Ok(()) => {
                return Ok(BackendBootstrapLock {
                    path: lock_path,
                    owner,
                });
            }
            Err(error) if error.kind() == ErrorKind::AlreadyExists => {
                if !lock_owner_is_alive(&lock_path) {
                    let _ = fs::remove_file(&lock_path);
                    continue;
                }
                if Instant::now() >= deadline {
                    return Err(format!(
                        "wait backend bootstrap lock timeout after {timeout_ms}ms"
                    ));
                }
                thread::sleep(Duration::from_millis(LOCK_WAIT_INTERVAL_MS));
            }
            Err(error) => {
                return Err(format!(
                    "create backend bootstrap lock failed: {} ({error})",
                    lock_path.display()
                ));
            }
        }
    }
}

pub fn process_is_alive(pid: u32) -> bool {
    if pid == 0 {
        return false;
    }
    run_status("kill", &["-0", &pid.to_string()])
}

pub fn process_start_token(pid: u32) -> Option<String> {
    if pid == 0 {
        return None;
    }
    let output = Command::new(resolve_ps_path())
        .args(["-p", &pid.to_string(), "-o", "lstart="])
        .output()
        .ok()?;
    if !output.status.success() {
        return None;
    }
    let token = String::from_utf8_lossy(&output.stdout).trim().to_string();
    if token.is_empty() {
        return None;
    }
    Some(token)
}

pub fn kill_process_tree(pid: u32) -> Result<(), String> {
    if pid == 0 {
        return Ok(());
    }

    let mut process_tree = collect_descendant_pids(pid);
    process_tree.push(pid);

    send_signal_to_pids("TERM", &process_tree);
    if wait_for_all_exit(&process_tree, Duration::from_millis(PROCESS_EXIT_TIMEOUT_MS)) {
        return Ok(());
    }

    let alive_after_term: Vec<u32> = process_tree
        .iter()
        .copied()
        .filter(|candidate| process_is_alive(*candidate))
        .collect();
    send_signal_to_pids("KILL", &alive_after_term);
    if wait_for_all_exit(
        &alive_after_term,
        Duration::from_millis(PROCESS_FORCE_KILL_TIMEOUT_MS),
    ) {
        return Ok(());
    }

    let remaining: Vec<String> = alive_after_term
        .into_iter()
        .filter(|candidate| process_is_alive(*candidate))
        .map(|candidate| candidate.to_string())
        .collect();
    if remaining.is_empty() {
        return Ok(());
    }
    Err(format!(
        "kill process tree failed pid={pid}: remaining pids {}",
        remaining.join(",")
    ))
}

fn collect_descendant_pids(root_pid: u32) -> Vec<u32> {
    let output = match Command::new(resolve_ps_path())
        .args(["-axo", "pid=,ppid="])
        .output()
    {
        Ok(output) if output.status.success() => output,
        _ => return Vec::new(),
    };

    let mut pairs = Vec::new();
    for line in String::from_utf8_lossy(&output.stdout).lines() {
        let mut parts = line.split_whitespace();
        let Some(pid_raw) = parts.next() else {
            continue;
        };
        let Some(ppid_raw) = parts.next() else {
            continue;
        };
        let Ok(pid) = pid_raw.parse::<u32>() else {
            continue;
        };
        let Ok(ppid) = ppid_raw.parse::<u32>() else {
            continue;
        };
        pairs.push((pid, ppid));
    }

    let mut descendants = Vec::new();
    let mut stack = vec![root_pid];
    while let Some(parent_pid) = stack.pop() {
        let mut direct_children: Vec<u32> = pairs
            .iter()
            .filter(|(_, ppid)| *ppid == parent_pid)
            .map(|(pid, _)| *pid)
            .collect();
        direct_children.sort_unstable();
        for child_pid in &direct_children {
            stack.push(*child_pid);
        }
        descendants.extend(direct_children);
    }
    descendants
}

fn wait_for_all_exit(pids: &[u32], timeout: Duration) -> bool {
    let deadline = Instant::now() + timeout;
    while Instant::now() < deadline {
        if pids.iter().all(|pid| !process_is_alive(*pid)) {
            return true;
        }
        thread::sleep(Duration::from_millis(100));
    }
    pids.iter().all(|pid| !process_is_alive(*pid))
}

fn send_signal_to_pids(signal: &str, pids: &[u32]) {
    for pid in pids.iter().rev() {
        if *pid == 0 || !process_is_alive(*pid) {
            continue;
        }
        let flag = format!("-{signal}");
        let _ = Command::new("kill").args([flag.as_str(), &pid.to_string()]).status();
    }
}

fn lock_path_for_name(lock_name: &str) -> Result<PathBuf, String> {
    let lock_dir = env::temp_dir().join("com.wechatauto.shell").join("locks");
    fs::create_dir_all(&lock_dir)
        .map_err(|error| format!("create lock dir failed: {} ({error})", lock_dir.display()))?;
    Ok(lock_dir.join(format!("{}.lock", sanitize_lock_name(lock_name))))
}

fn sanitize_lock_name(lock_name: &str) -> String {
    let mut sanitized = String::with_capacity(lock_name.len());
    for ch in lock_name.chars() {
        if ch.is_ascii_alphanumeric() || ch == '-' || ch == '_' || ch == '.' {
            sanitized.push(ch);
        } else {
            sanitized.push('_');
        }
    }
    if sanitized.is_empty() {
        return "backend-bootstrap".to_string();
    }
    sanitized
}

fn try_create_lock(path: &PathBuf, owner: &LockOwner) -> Result<(), std::io::Error> {
    let content = serde_json::to_string(owner)
        .map_err(|error| std::io::Error::new(ErrorKind::Other, error.to_string()))?;
    let mut file = OpenOptions::new().write(true).create_new(true).open(path)?;
    file.write_all(content.as_bytes())?;
    file.flush()?;
    Ok(())
}

fn read_lock_owner(path: &PathBuf) -> Option<LockOwner> {
    let content = fs::read_to_string(path).ok()?;
    serde_json::from_str::<LockOwner>(&content).ok()
}

fn lock_owner_is_alive(path: &PathBuf) -> bool {
    let Some(owner) = read_lock_owner(path) else {
        return false;
    };
    if !process_is_alive(owner.pid) {
        return false;
    }
    if owner.start_token.is_empty() {
        return true;
    }
    process_start_token(owner.pid)
        .map(|current| current == owner.start_token)
        .unwrap_or(false)
}

fn run_status(command: &str, args: &[&str]) -> bool {
    Command::new(command)
        .args(args)
        .status()
        .map(|status| status.success())
        .unwrap_or(false)
}

fn resolve_ps_path() -> &'static str {
    "/bin/ps"
}

#[cfg(test)]
mod tests {
    use super::sanitize_lock_name;

    #[test]
    fn sanitize_lock_name_replaces_windows_only_separators() {
        assert_eq!(
            sanitize_lock_name(r"Local\com.wechatauto.shell/backend-bootstrap"),
            "Local_com.wechatauto.shell_backend-bootstrap"
        );
    }

    #[test]
    fn sanitize_lock_name_preserves_safe_characters() {
        assert_eq!(
            sanitize_lock_name("com.wechatauto.shell.backend-bootstrap.1234"),
            "com.wechatauto.shell.backend-bootstrap.1234"
        );
    }
}
