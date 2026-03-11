use std::{
    collections::hash_map::DefaultHasher,
    fs,
    fs::OpenOptions,
    hash::{Hash, Hasher},
    io::Write,
    path::{Path, PathBuf},
    sync::{
        atomic::{AtomicBool, Ordering},
        Arc, Mutex,
    },
    thread,
    time::{Duration, Instant},
};

use serde::{Deserialize, Serialize};
use tauri::{Manager, Runtime, State};
use tauri_plugin_shell::{
    process::{CommandChild, CommandEvent},
    ShellExt,
};

use crate::backend::win32::{
    acquire_bootstrap_lock, process_is_alive, process_start_token, BackendBootstrapLock,
};
use crate::backend_health::probe_backend_health;

const BACKEND_HOST: &str = "127.0.0.1";
const BACKEND_HTTP_PORT: u16 = 8765;
const BACKEND_WS_PORT: u16 = 8766;
const BACKEND_READY_TIMEOUT_SECONDS: u64 = 15;
const BACKEND_READY_POLL_INTERVAL_MS: u64 = 250;
const BACKEND_BOOTSTRAP_LOCK_TIMEOUT_MS: u32 = 20_000;
const BACKEND_SIDECAR_NAME: &str = "wechat-auto-backend";
const BACKEND_BOOTSTRAP_MUTEX_NAMESPACE: &str = "Local\\com.wechatauto.shell.backend-bootstrap";
const BACKEND_MARKER_FILE: &str = "backend-sidecar.json";

#[derive(Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct BackendConnectionInfo {
    http_base_url: String,
    ws_url: String,
    managed: bool,
    startup_error: String,
    runtime_root: String,
}

#[derive(Clone, Deserialize, Serialize)]
struct BackendPidMarker {
    pid: u32,
    start_token: String,
}

pub struct ManagedBackendState {
    child: Mutex<Option<CommandChild>>,
    owns_child: bool,
    info: BackendConnectionInfo,
    runtime_root: PathBuf,
    marker: Option<BackendPidMarker>,
}

impl ManagedBackendState {
    fn new(
        info: BackendConnectionInfo,
        child: Option<CommandChild>,
        owns_child: bool,
        runtime_root: PathBuf,
        marker: Option<BackendPidMarker>,
    ) -> Self {
        Self {
            child: Mutex::new(child),
            owns_child,
            info,
            runtime_root,
            marker,
        }
    }

    pub fn kill_owned_child(&self) {
        if !self.owns_child {
            return;
        }
        if let Some(marker) = self.marker.as_ref() {
            clear_backend_marker_if_matches(&self.runtime_root, Some(marker));
        }
        let mut guard = self.child.lock().unwrap();
        if let Some(child) = guard.take() {
            let _ = child.kill();
        }
    }
}

enum BackendWaitResult {
    Ready,
    Exited,
    StillStarting,
}

#[tauri::command]
pub fn get_backend_connection_info(state: State<'_, ManagedBackendState>) -> BackendConnectionInfo {
    state.info.clone()
}

pub fn bootstrap_backend<R: Runtime>(app: &tauri::App<R>) -> ManagedBackendState {
    let runtime_root = match managed_runtime_root(app.path().app_local_data_dir()) {
        Ok(path) => path,
        Err(error) => {
            eprintln!("[backend-bootstrap] {error}");
            return ManagedBackendState::new(
                build_backend_info(Path::new(""), false, error),
                None,
                false,
                PathBuf::new(),
                None,
            );
        }
    };

    append_bootstrap_log(
        &runtime_root,
        &format!("bootstrap start runtime_root={}", runtime_root.display()),
    );

    if probe_backend_health(BACKEND_HTTP_PORT) {
        append_bootstrap_log(&runtime_root, "reuse existing backend on fixed ports");
        return ManagedBackendState::new(
            build_backend_info(&runtime_root, false, String::new()),
            None,
            false,
            runtime_root,
            None,
        );
    }

    let _bootstrap_lock = match acquire_backend_bootstrap_lock(&runtime_root) {
        Ok(lock) => lock,
        Err(error) => {
            eprintln!("[backend-bootstrap] {error}");
            append_bootstrap_log(&runtime_root, &format!("bootstrap failed: {error}"));
            return ManagedBackendState::new(
                build_backend_info(&runtime_root, false, error),
                None,
                false,
                runtime_root,
                None,
            );
        }
    };

    if probe_backend_health(BACKEND_HTTP_PORT) {
        append_bootstrap_log(&runtime_root, "reuse existing backend after bootstrap lock");
        return ManagedBackendState::new(
            build_backend_info(&runtime_root, false, String::new()),
            None,
            false,
            runtime_root,
            None,
        );
    }

    if let Some(marker) = read_backend_marker(&runtime_root) {
        if backend_marker_is_alive(&marker) {
            match wait_for_existing_backend(&runtime_root, &marker) {
                BackendWaitResult::Ready => {
                    return ManagedBackendState::new(
                        build_backend_info(&runtime_root, false, String::new()),
                        None,
                        false,
                        runtime_root,
                        None,
                    );
                }
                BackendWaitResult::StillStarting => {
                    return ManagedBackendState::new(
                        build_backend_info(&runtime_root, true, String::new()),
                        None,
                        false,
                        runtime_root,
                        None,
                    );
                }
                BackendWaitResult::Exited => {}
            }
        } else {
            append_bootstrap_log(
                &runtime_root,
                &format!(
                    "remove stale backend marker pid={} token={}",
                    marker.pid, marker.start_token
                ),
            );
            clear_backend_marker_if_matches(&runtime_root, Some(&marker));
        }
    }

    match spawn_backend_sidecar(app, &runtime_root) {
        Ok((child, marker)) => ManagedBackendState::new(
            build_backend_info(&runtime_root, true, String::new()),
            Some(child),
            true,
            runtime_root.clone(),
            Some(marker),
        ),
        Err(error) => {
            eprintln!("[backend-bootstrap] {error}");
            append_bootstrap_log(&runtime_root, &format!("bootstrap failed: {error}"));
            ManagedBackendState::new(
                build_backend_info(&runtime_root, false, error),
                None,
                false,
                runtime_root,
                None,
            )
        }
    }
}

pub fn log_single_instance_event<R: Runtime>(app: &tauri::AppHandle<R>, message: &str) {
    if let Ok(runtime_root) = managed_runtime_root(app.path().app_local_data_dir()) {
        append_bootstrap_log(&runtime_root, message);
    }
}

fn build_backend_info(
    runtime_root: &Path,
    managed: bool,
    startup_error: String,
) -> BackendConnectionInfo {
    BackendConnectionInfo {
        http_base_url: format!("http://{BACKEND_HOST}:{BACKEND_HTTP_PORT}"),
        ws_url: format!("ws://{BACKEND_HOST}:{BACKEND_WS_PORT}/events"),
        managed,
        startup_error,
        runtime_root: runtime_root.display().to_string(),
    }
}

fn append_bootstrap_log(runtime_root: &Path, message: &str) {
    let logs_dir = runtime_root.join("logs");
    if fs::create_dir_all(&logs_dir).is_err() {
        return;
    }
    let log_path = logs_dir.join("desktop-shell-bootstrap.log");
    let mut file = match OpenOptions::new().create(true).append(true).open(log_path) {
        Ok(file) => file,
        Err(_) => return,
    };
    let _ = writeln!(file, "{message}");
}

fn managed_runtime_root(runtime_root: Result<PathBuf, tauri::Error>) -> Result<PathBuf, String> {
    let runtime_root =
        runtime_root.map_err(|err| format!("resolve app_local_data_dir failed: {err}"))?;
    fs::create_dir_all(&runtime_root).map_err(|err| {
        format!(
            "create runtime root failed: {} ({err})",
            runtime_root.display()
        )
    })?;
    Ok(runtime_root)
}

fn runtime_state_dir(runtime_root: &Path) -> PathBuf {
    runtime_root.join("logs").join(".runtime")
}

fn backend_marker_path(runtime_root: &Path) -> PathBuf {
    runtime_state_dir(runtime_root).join(BACKEND_MARKER_FILE)
}

fn build_backend_bootstrap_mutex_name(runtime_root: &Path) -> String {
    let mut hasher = DefaultHasher::new();
    runtime_root.to_string_lossy().hash(&mut hasher);
    format!(
        "{BACKEND_BOOTSTRAP_MUTEX_NAMESPACE}.{:016x}",
        hasher.finish()
    )
}

fn acquire_backend_bootstrap_lock(runtime_root: &Path) -> Result<BackendBootstrapLock, String> {
    let mutex_name = build_backend_bootstrap_mutex_name(runtime_root);
    acquire_bootstrap_lock(&mutex_name, BACKEND_BOOTSTRAP_LOCK_TIMEOUT_MS)
}

fn build_backend_pid_marker(pid: u32) -> Result<BackendPidMarker, String> {
    let start_token = process_start_token(pid)
        .ok_or_else(|| format!("query backend sidecar start token failed pid={pid}"))?;
    Ok(BackendPidMarker { pid, start_token })
}

fn backend_marker_is_alive(marker: &BackendPidMarker) -> bool {
    if !process_is_alive(marker.pid) {
        return false;
    }
    process_start_token(marker.pid)
        .map(|token| token == marker.start_token)
        .unwrap_or(false)
}

fn read_backend_marker(runtime_root: &Path) -> Option<BackendPidMarker> {
    let marker_path = backend_marker_path(runtime_root);
    let content = fs::read_to_string(marker_path).ok()?;
    serde_json::from_str::<BackendPidMarker>(&content).ok()
}

fn write_backend_marker(runtime_root: &Path, marker: &BackendPidMarker) -> Result<(), String> {
    let state_dir = runtime_state_dir(runtime_root);
    fs::create_dir_all(&state_dir).map_err(|err| {
        format!(
            "create runtime state dir failed: {} ({err})",
            state_dir.display()
        )
    })?;
    let marker_path = backend_marker_path(runtime_root);
    let content = serde_json::to_vec(marker)
        .map_err(|err| format!("serialize backend pid marker failed: {err}"))?;
    fs::write(&marker_path, content).map_err(|err| {
        format!(
            "write backend pid marker failed: {} ({err})",
            marker_path.display()
        )
    })
}

fn clear_backend_marker_if_matches(runtime_root: &Path, expected: Option<&BackendPidMarker>) {
    let marker_path = backend_marker_path(runtime_root);
    if !marker_path.exists() {
        return;
    }
    if let Some(expected_marker) = expected {
        let Some(current_marker) = read_backend_marker(runtime_root) else {
            return;
        };
        if current_marker.pid != expected_marker.pid
            || current_marker.start_token != expected_marker.start_token
        {
            return;
        }
    }
    let _ = fs::remove_file(marker_path);
}

fn wait_for_backend_ready<F>(mut is_exited: F) -> BackendWaitResult
where
    F: FnMut() -> bool,
{
    let deadline = Instant::now() + Duration::from_secs(BACKEND_READY_TIMEOUT_SECONDS);
    while Instant::now() < deadline {
        if probe_backend_health(BACKEND_HTTP_PORT) {
            return BackendWaitResult::Ready;
        }
        if is_exited() {
            return BackendWaitResult::Exited;
        }
        thread::sleep(Duration::from_millis(BACKEND_READY_POLL_INTERVAL_MS));
    }

    if probe_backend_health(BACKEND_HTTP_PORT) {
        return BackendWaitResult::Ready;
    }
    if is_exited() {
        return BackendWaitResult::Exited;
    }
    BackendWaitResult::StillStarting
}

fn wait_for_existing_backend(runtime_root: &Path, marker: &BackendPidMarker) -> BackendWaitResult {
    append_bootstrap_log(
        runtime_root,
        &format!(
            "reuse backend marker pid={} token={} and wait for readiness",
            marker.pid, marker.start_token
        ),
    );
    match wait_for_backend_ready(|| !backend_marker_is_alive(marker)) {
        BackendWaitResult::Ready => {
            append_bootstrap_log(
                runtime_root,
                &format!("existing backend ready pid={}", marker.pid),
            );
            BackendWaitResult::Ready
        }
        BackendWaitResult::Exited => {
            append_bootstrap_log(
                runtime_root,
                &format!("existing backend exited before ready pid={}", marker.pid),
            );
            clear_backend_marker_if_matches(runtime_root, Some(marker));
            BackendWaitResult::Exited
        }
        BackendWaitResult::StillStarting => {
            append_bootstrap_log(
                runtime_root,
                &format!(
                    "existing backend still starting after {}s pid={}, skip duplicate spawn",
                    BACKEND_READY_TIMEOUT_SECONDS, marker.pid
                ),
            );
            BackendWaitResult::StillStarting
        }
    }
}

fn spawn_backend_sidecar<R: Runtime>(
    app: &tauri::App<R>,
    runtime_root: &Path,
) -> Result<(CommandChild, BackendPidMarker), String> {
    let config_path = runtime_root.join("config").join("listener.json");
    let runtime_root_value = runtime_root.display().to_string();
    append_bootstrap_log(
        runtime_root,
        &format!(
            "spawning backend sidecar config={} runtime_root={}",
            config_path.display(),
            runtime_root.display()
        ),
    );

    let sidecar_command = app
        .shell()
        .sidecar(BACKEND_SIDECAR_NAME)
        .map_err(|err| format!("prepare backend sidecar failed: {err}"))?
        .args([
            "--config",
            config_path.to_string_lossy().as_ref(),
            "--host",
            BACKEND_HOST,
            "--http-port",
            "8765",
            "--ws-port",
            "8766",
        ])
        .env("WECHAT_AUTO_RUNTIME_ROOT", &runtime_root_value)
        .current_dir(runtime_root);

    let (mut rx, child) = sidecar_command
        .spawn()
        .map_err(|err| format!("spawn backend sidecar failed: {err}"))?;

    let marker = match build_backend_pid_marker(child.pid()) {
        Ok(marker) => marker,
        Err(error) => {
            let _ = child.kill();
            return Err(error);
        }
    };
    if let Err(error) = write_backend_marker(runtime_root, &marker) {
        let _ = child.kill();
        return Err(error);
    }
    append_bootstrap_log(
        runtime_root,
        &format!(
            "spawned backend sidecar pid={} token={}",
            marker.pid, marker.start_token
        ),
    );

    let terminated_ref = Arc::new(AtomicBool::new(false));
    let terminated_flag = terminated_ref.clone();
    let log_root = runtime_root.to_path_buf();
    let marker_for_events = marker.clone();

    tauri::async_runtime::spawn(async move {
        while let Some(event) = rx.recv().await {
            match event {
                CommandEvent::Stdout(line) => {
                    let text = String::from_utf8_lossy(&line).trim().to_string();
                    if !text.is_empty() {
                        println!("[backend-sidecar stdout] {text}");
                        append_bootstrap_log(&log_root, &format!("backend stdout: {text}"));
                    }
                }
                CommandEvent::Stderr(line) => {
                    let text = String::from_utf8_lossy(&line).trim().to_string();
                    if !text.is_empty() {
                        eprintln!("[backend-sidecar stderr] {text}");
                        append_bootstrap_log(&log_root, &format!("backend stderr: {text}"));
                    }
                }
                CommandEvent::Error(error) => {
                    terminated_flag.store(true, Ordering::SeqCst);
                    clear_backend_marker_if_matches(&log_root, Some(&marker_for_events));
                    eprintln!("[backend-sidecar error] {error}");
                    append_bootstrap_log(&log_root, &format!("backend error: {error}"));
                }
                CommandEvent::Terminated(payload) => {
                    terminated_flag.store(true, Ordering::SeqCst);
                    clear_backend_marker_if_matches(&log_root, Some(&marker_for_events));
                    eprintln!(
                        "[backend-sidecar terminated] code={:?} signal={:?}",
                        payload.code, payload.signal
                    );
                    append_bootstrap_log(
                        &log_root,
                        &format!(
                            "backend terminated code={:?} signal={:?}",
                            payload.code, payload.signal
                        ),
                    );
                }
                _ => {}
            }
        }
    });

    match wait_for_backend_ready(|| terminated_ref.load(Ordering::SeqCst)) {
        BackendWaitResult::Ready => {
            append_bootstrap_log(
                runtime_root,
                &format!("backend sidecar ready pid={}", marker.pid),
            );
            Ok((child, marker))
        }
        BackendWaitResult::Exited => {
            clear_backend_marker_if_matches(runtime_root, Some(&marker));
            let _ = child.kill();
            Err("backend sidecar exited before /healthz became ready".to_string())
        }
        BackendWaitResult::StillStarting => {
            append_bootstrap_log(
                runtime_root,
                &format!(
                    "backend sidecar still starting after {}s pid={}, continue without duplicate spawn",
                    BACKEND_READY_TIMEOUT_SECONDS, marker.pid
                ),
            );
            Ok((child, marker))
        }
    }
}
