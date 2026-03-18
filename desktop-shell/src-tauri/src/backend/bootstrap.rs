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
    acquire_bootstrap_lock, kill_process_tree, process_is_alive, process_start_token,
    BackendBootstrapLock,
};
use crate::backend_health::{describe_health_snapshot, probe_backend_health, BackendHealthProbe};

const BACKEND_HOST: &str = "127.0.0.1";
const BACKEND_HTTP_PORT: u16 = 8765;
const BACKEND_WS_PORT: u16 = 8766;
const BACKEND_READY_TIMEOUT_SECONDS: u64 = 15;
const BACKEND_READY_POLL_INTERVAL_MS: u64 = 250;
const BACKEND_BOOTSTRAP_LOCK_TIMEOUT_MS: u32 = 20_000;
const BACKEND_SIDECAR_NAME: &str = "wechat-auto-backend";
const BACKEND_BOOTSTRAP_MUTEX_NAMESPACE: &str = "Local\\com.wechatauto.shell.backend-bootstrap";
const BACKEND_MARKER_FILE: &str = "backend-sidecar.json";
const BACKEND_OWNER_PID_ENV: &str = "WECHAT_AUTO_OWNER_PID";
const BACKEND_OWNER_START_TOKEN_ENV: &str = "WECHAT_AUTO_OWNER_START_TOKEN";

#[derive(Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct BackendConnectionInfo {
    http_base_url: String,
    ws_url: String,
    managed: bool,
    owns_backend: bool,
    restart_supported: bool,
    startup_error: String,
    runtime_root: String,
}

#[derive(Clone, Deserialize, Serialize)]
struct BackendPidMarker {
    pid: u32,
    start_token: String,
}

struct ManagedBackendMetadata {
    owns_child: bool,
    info: BackendConnectionInfo,
    marker: Option<BackendPidMarker>,
}

pub struct ManagedBackendState {
    child: Mutex<Option<CommandChild>>,
    metadata: Mutex<ManagedBackendMetadata>,
    runtime_root: PathBuf,
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
            metadata: Mutex::new(ManagedBackendMetadata {
                owns_child,
                info,
                marker,
            }),
            runtime_root,
        }
    }

    pub fn connection_info(&self) -> BackendConnectionInfo {
        self.metadata.lock().unwrap().info.clone()
    }

    fn replace_backend_state(
        &self,
        info: BackendConnectionInfo,
        child: Option<CommandChild>,
        owns_child: bool,
        marker: Option<BackendPidMarker>,
    ) {
        *self.child.lock().unwrap() = child;
        *self.metadata.lock().unwrap() = ManagedBackendMetadata {
            owns_child,
            info,
            marker,
        };
    }

    pub fn kill_owned_child(&self) {
        let marker = {
            let metadata = self.metadata.lock().unwrap();
            if !metadata.owns_child {
                return;
            }
            metadata.marker.clone()
        };
        if let Some(marker) = marker.as_ref() {
            clear_backend_marker_if_matches(&self.runtime_root, Some(marker));
        }
        let mut guard = self.child.lock().unwrap();
        let child = guard.take();
        let pid = child
            .as_ref()
            .map(CommandChild::pid)
            .or_else(|| marker.as_ref().map(|value| value.pid));
        let Some(pid) = pid else {
            return;
        };
        match kill_process_tree(pid) {
            Ok(()) => append_bootstrap_log(
                &self.runtime_root,
                &format!("killed owned backend process tree pid={pid}"),
            ),
            Err(error) => {
                append_bootstrap_log(
                    &self.runtime_root,
                    &format!("kill owned backend process tree failed pid={pid}: {error}"),
                );
                if let Some(child) = child {
                    let _ = child.kill();
                }
            }
        }
    }

    fn take_owned_child_for_restart(&self) -> Result<(CommandChild, BackendPidMarker), String> {
        let marker = {
            let metadata = self.metadata.lock().unwrap();
            if !metadata.owns_child
                || !metadata.info.owns_backend
                || !metadata.info.restart_supported
            {
                return Err("backend is not owned by the current shell".to_string());
            }
            metadata
                .marker
                .clone()
                .ok_or_else(|| "owned backend marker is missing".to_string())?
        };
        clear_backend_marker_if_matches(&self.runtime_root, Some(&marker));
        let child = {
            let mut guard = self.child.lock().unwrap();
            guard
                .take()
                .ok_or_else(|| "owned backend child handle is missing".to_string())?
        };
        self.replace_backend_state(
            build_backend_info(&self.runtime_root, true, false, false, String::new()),
            None,
            false,
            None,
        );
        Ok((child, marker))
    }

    fn set_restart_failure(&self, error: String) {
        self.replace_backend_state(
            build_backend_info(&self.runtime_root, false, false, false, error),
            None,
            false,
            None,
        );
    }

    pub fn restart_owned_backend<R: Runtime>(
        &self,
        app: &tauri::AppHandle<R>,
    ) -> Result<BackendConnectionInfo, String> {
        let _bootstrap_lock = acquire_backend_bootstrap_lock(&self.runtime_root)?;
        let (child, marker) = self.take_owned_child_for_restart()?;
        child.kill().map_err(|err| {
            let message = format!("kill owned backend failed: {err}");
            self.set_restart_failure(message.clone());
            message
        })?;
        wait_for_backend_exit(&marker).map_err(|error| {
            self.set_restart_failure(error.clone());
            error
        })?;

        match spawn_backend_sidecar(app, &self.runtime_root) {
            Ok((child, marker)) => {
                let info = build_backend_info(&self.runtime_root, true, true, true, String::new());
                self.replace_backend_state(info.clone(), Some(child), true, Some(marker));
                Ok(info)
            }
            Err(error) => {
                self.set_restart_failure(error.clone());
                Err(error)
            }
        }
    }
}

enum BackendWaitResult {
    Ready,
    Exited,
    StillStarting(Option<String>),
    Failed(String),
}

#[tauri::command]
pub fn get_backend_connection_info(state: State<'_, ManagedBackendState>) -> BackendConnectionInfo {
    state.connection_info()
}

#[tauri::command]
pub fn restart_owned_backend<R: Runtime>(
    app: tauri::AppHandle<R>,
    state: State<'_, ManagedBackendState>,
) -> Result<BackendConnectionInfo, String> {
    state.restart_owned_backend(&app)
}

pub fn bootstrap_backend<R: Runtime>(app: &tauri::App<R>) -> ManagedBackendState {
    let runtime_root = match managed_runtime_root(app.path().app_local_data_dir()) {
        Ok(path) => path,
        Err(error) => {
            eprintln!("[backend-bootstrap] {error}");
            return ManagedBackendState::new(
                build_backend_info(Path::new(""), false, false, false, error),
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

    if let Some(state) = resolve_existing_fixed_port_backend(&runtime_root) {
        return state;
    }

    let _bootstrap_lock = match acquire_backend_bootstrap_lock(&runtime_root) {
        Ok(lock) => lock,
        Err(error) => {
            eprintln!("[backend-bootstrap] {error}");
            append_bootstrap_log(&runtime_root, &format!("bootstrap failed: {error}"));
            return ManagedBackendState::new(
                build_backend_info(&runtime_root, false, false, false, error),
                None,
                false,
                runtime_root,
                None,
            );
        }
    };

    if let Some(state) = resolve_existing_fixed_port_backend(&runtime_root) {
        return state;
    }

    if let Some(marker) = read_backend_marker(&runtime_root) {
        if backend_marker_is_alive(&marker) {
            match wait_for_existing_backend(&runtime_root, &marker) {
                BackendWaitResult::Ready => {
                    return ManagedBackendState::new(
                        build_backend_info(&runtime_root, false, false, false, String::new()),
                        None,
                        false,
                        runtime_root,
                        None,
                    );
                }
                BackendWaitResult::StillStarting(_) => {
                    return ManagedBackendState::new(
                        build_backend_info(&runtime_root, true, false, false, String::new()),
                        None,
                        false,
                        runtime_root,
                        None,
                    );
                }
                BackendWaitResult::Failed(error) => {
                    append_bootstrap_log(
                        &runtime_root,
                        &format!("existing backend health failed: {error}"),
                    );
                    return ManagedBackendState::new(
                        build_backend_info(&runtime_root, false, false, false, error),
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

    match spawn_backend_sidecar(&app.handle(), &runtime_root) {
        Ok((child, marker)) => ManagedBackendState::new(
            build_backend_info(&runtime_root, true, true, true, String::new()),
            Some(child),
            true,
            runtime_root.clone(),
            Some(marker),
        ),
        Err(error) => {
            eprintln!("[backend-bootstrap] {error}");
            append_bootstrap_log(&runtime_root, &format!("bootstrap failed: {error}"));
            ManagedBackendState::new(
                build_backend_info(&runtime_root, false, false, false, error),
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
    owns_backend: bool,
    restart_supported: bool,
    startup_error: String,
) -> BackendConnectionInfo {
    BackendConnectionInfo {
        http_base_url: format!("http://{BACKEND_HOST}:{BACKEND_HTTP_PORT}"),
        ws_url: format!("ws://{BACKEND_HOST}:{BACKEND_WS_PORT}/events"),
        managed,
        owns_backend,
        restart_supported,
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

fn wait_for_backend_exit(marker: &BackendPidMarker) -> Result<(), String> {
    let deadline = Instant::now() + Duration::from_secs(5);
    while Instant::now() < deadline {
        if !backend_marker_is_alive(marker) {
            return Ok(());
        }
        thread::sleep(Duration::from_millis(100));
    }
    Err(format!(
        "owned backend did not exit after restart request pid={}",
        marker.pid
    ))
}

fn build_fixed_port_failure_state(runtime_root: &Path, error: String) -> ManagedBackendState {
    append_bootstrap_log(&runtime_root, &format!("bootstrap failed: {error}"));
    ManagedBackendState::new(
        build_backend_info(runtime_root, false, false, false, error),
        None,
        false,
        runtime_root.to_path_buf(),
        None,
    )
}

fn resolve_existing_fixed_port_backend(runtime_root: &Path) -> Option<ManagedBackendState> {
    match probe_backend_health(BACKEND_HTTP_PORT) {
        BackendHealthProbe::Unreachable => None,
        BackendHealthProbe::Invalid(error) => Some(build_fixed_port_failure_state(
            runtime_root,
            format!("existing backend health probe invalid: {error}"),
        )),
        BackendHealthProbe::Reachable(snapshot) if snapshot.status.is_ready() => {
            append_bootstrap_log(&runtime_root, "reuse existing backend on fixed ports");
            Some(ManagedBackendState::new(
                build_backend_info(runtime_root, false, false, false, String::new()),
                None,
                false,
                runtime_root.to_path_buf(),
                None,
            ))
        }
        BackendHealthProbe::Reachable(snapshot) if snapshot.status.is_retryable() => {
            append_bootstrap_log(
                runtime_root,
                &format!(
                    "existing backend on fixed ports not ready yet, wait for readiness {}",
                    describe_health_snapshot(&snapshot)
                ),
            );
            match wait_for_backend_ready(|| false) {
                BackendWaitResult::Ready => Some(ManagedBackendState::new(
                    build_backend_info(runtime_root, false, false, false, String::new()),
                    None,
                    false,
                    runtime_root.to_path_buf(),
                    None,
                )),
                BackendWaitResult::StillStarting(detail) => {
                    if let Some(summary) = detail {
                        append_bootstrap_log(
                            runtime_root,
                            &format!(
                                "existing backend on fixed ports still starting after {}s {}",
                                BACKEND_READY_TIMEOUT_SECONDS, summary
                            ),
                        );
                    } else {
                        append_bootstrap_log(
                            runtime_root,
                            &format!(
                                "existing backend on fixed ports still starting after {}s",
                                BACKEND_READY_TIMEOUT_SECONDS
                            ),
                        );
                    }
                    Some(ManagedBackendState::new(
                        build_backend_info(runtime_root, true, false, false, String::new()),
                        None,
                        false,
                        runtime_root.to_path_buf(),
                        None,
                    ))
                }
                BackendWaitResult::Failed(error) => {
                    Some(build_fixed_port_failure_state(runtime_root, error))
                }
                BackendWaitResult::Exited => Some(build_fixed_port_failure_state(
                    runtime_root,
                    "existing backend on fixed ports exited before /healthz became ready"
                        .to_string(),
                )),
            }
        }
        BackendHealthProbe::Reachable(snapshot) => Some(build_fixed_port_failure_state(
            runtime_root,
            format!(
                "existing backend on fixed ports is not ready: {}",
                describe_health_snapshot(&snapshot)
            ),
        )),
    }
}

fn wait_for_backend_ready<F>(mut is_exited: F) -> BackendWaitResult
where
    F: FnMut() -> bool,
{
    let deadline = Instant::now() + Duration::from_secs(BACKEND_READY_TIMEOUT_SECONDS);
    let mut last_starting_detail: Option<String> = None;
    while Instant::now() < deadline {
        match probe_backend_health(BACKEND_HTTP_PORT) {
            BackendHealthProbe::Reachable(snapshot) if snapshot.status.is_ready() => {
                return BackendWaitResult::Ready;
            }
            BackendHealthProbe::Reachable(snapshot) if snapshot.status.is_retryable() => {
                last_starting_detail = Some(describe_health_snapshot(&snapshot));
            }
            BackendHealthProbe::Reachable(snapshot) => {
                return BackendWaitResult::Failed(format!(
                    "backend /healthz reported {}",
                    describe_health_snapshot(&snapshot)
                ));
            }
            BackendHealthProbe::Invalid(error) => {
                return BackendWaitResult::Failed(format!(
                    "backend /healthz returned invalid response: {error}"
                ));
            }
            BackendHealthProbe::Unreachable => {}
        }
        if is_exited() {
            return BackendWaitResult::Exited;
        }
        thread::sleep(Duration::from_millis(BACKEND_READY_POLL_INTERVAL_MS));
    }

    match probe_backend_health(BACKEND_HTTP_PORT) {
        BackendHealthProbe::Reachable(snapshot) if snapshot.status.is_ready() => {
            return BackendWaitResult::Ready;
        }
        BackendHealthProbe::Reachable(snapshot) if snapshot.status.is_retryable() => {
            last_starting_detail = Some(describe_health_snapshot(&snapshot));
        }
        BackendHealthProbe::Reachable(snapshot) => {
            return BackendWaitResult::Failed(format!(
                "backend /healthz reported {}",
                describe_health_snapshot(&snapshot)
            ));
        }
        BackendHealthProbe::Invalid(error) => {
            return BackendWaitResult::Failed(format!(
                "backend /healthz returned invalid response: {error}"
            ));
        }
        BackendHealthProbe::Unreachable => {}
    }
    if is_exited() {
        return BackendWaitResult::Exited;
    }
    BackendWaitResult::StillStarting(last_starting_detail)
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
        BackendWaitResult::StillStarting(detail) => {
            let suffix = detail
                .as_ref()
                .map(|value| format!(" {value}"))
                .unwrap_or_default();
            append_bootstrap_log(
                runtime_root,
                &format!(
                    "existing backend still starting after {}s pid={}, skip duplicate spawn{}",
                    BACKEND_READY_TIMEOUT_SECONDS, marker.pid, suffix
                ),
            );
            BackendWaitResult::StillStarting(detail)
        }
        BackendWaitResult::Failed(error) => {
            append_bootstrap_log(
                runtime_root,
                &format!("existing backend failed health readiness: {error}"),
            );
            BackendWaitResult::Failed(error)
        }
    }
}

fn spawn_backend_sidecar<R: Runtime>(
    app: &tauri::AppHandle<R>,
    runtime_root: &Path,
) -> Result<(CommandChild, BackendPidMarker), String> {
    let config_path = runtime_root.join("config").join("listener.json");
    let runtime_root_value = runtime_root.display().to_string();
    let owner_pid = std::process::id();
    let owner_pid_value = owner_pid.to_string();
    let owner_start_token = process_start_token(owner_pid).unwrap_or_default();
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
        .env(BACKEND_OWNER_PID_ENV, &owner_pid_value)
        .env(BACKEND_OWNER_START_TOKEN_ENV, &owner_start_token)
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
        BackendWaitResult::StillStarting(detail) => {
            let suffix = detail
                .as_ref()
                .map(|value| format!(" {value}"))
                .unwrap_or_default();
            append_bootstrap_log(
                runtime_root,
                &format!(
                    "backend sidecar still starting after {}s pid={}, continue without duplicate spawn{}",
                    BACKEND_READY_TIMEOUT_SECONDS, marker.pid, suffix
                ),
            );
            Ok((child, marker))
        }
        BackendWaitResult::Failed(error) => {
            clear_backend_marker_if_matches(runtime_root, Some(&marker));
            let _ = child.kill();
            Err(error)
        }
    }
}

#[cfg(test)]
mod tests {
    use std::path::Path;

    use super::{
        backend_marker_path, build_backend_bootstrap_mutex_name, build_backend_info,
        ManagedBackendState,
    };

    #[test]
    fn backend_bootstrap_mutex_name_is_stable_for_same_runtime_root() {
        let runtime_root = Path::new("C:/Users/test/AppData/Local/com.wechatauto.shell");
        assert_eq!(
            build_backend_bootstrap_mutex_name(runtime_root),
            build_backend_bootstrap_mutex_name(runtime_root)
        );
    }

    #[test]
    fn backend_bootstrap_mutex_name_changes_with_runtime_root() {
        let left = Path::new("C:/Users/test/AppData/Local/com.wechatauto.shell");
        let right = Path::new("D:/sandbox/com.wechatauto.shell");
        assert_ne!(
            build_backend_bootstrap_mutex_name(left),
            build_backend_bootstrap_mutex_name(right)
        );
    }

    #[test]
    fn backend_marker_path_stays_under_runtime_log_state_dir() {
        let runtime_root = Path::new("C:/Users/test/AppData/Local/com.wechatauto.shell");
        let marker_path = backend_marker_path(runtime_root);
        assert!(marker_path.ends_with("logs/.runtime/backend-sidecar.json"));
    }

    #[test]
    fn build_backend_info_marks_owned_managed_backend_as_restartable() {
        let runtime_root = Path::new("C:/Users/test/AppData/Local/com.wechatauto.shell");
        let info = build_backend_info(runtime_root, true, true, true, String::new());
        assert!(info.managed);
        assert!(info.owns_backend);
        assert!(info.restart_supported);
        assert!(info.startup_error.is_empty());
    }

    #[test]
    fn build_backend_info_marks_reused_backend_as_unowned() {
        let runtime_root = Path::new("C:/Users/test/AppData/Local/com.wechatauto.shell");
        let info = build_backend_info(runtime_root, false, false, false, String::new());
        assert!(!info.managed);
        assert!(!info.owns_backend);
        assert!(!info.restart_supported);
    }

    #[test]
    fn take_owned_child_for_restart_rejects_unowned_backend() {
        let runtime_root = Path::new("C:/Users/test/AppData/Local/com.wechatauto.shell");
        let state = ManagedBackendState::new(
            build_backend_info(runtime_root, true, false, false, String::new()),
            None,
            false,
            runtime_root.to_path_buf(),
            None,
        );
        match state.take_owned_child_for_restart() {
            Ok(_) => panic!("unowned backend should not pass restart gate"),
            Err(error) => assert_eq!(error, "backend is not owned by the current shell"),
        }
    }

    #[test]
    fn take_owned_child_for_restart_requires_owned_marker_after_passing_gate() {
        let runtime_root = Path::new("C:/Users/test/AppData/Local/com.wechatauto.shell");
        let state = ManagedBackendState::new(
            build_backend_info(runtime_root, true, true, true, String::new()),
            None,
            true,
            runtime_root.to_path_buf(),
            None,
        );
        match state.take_owned_child_for_restart() {
            Ok(_) => panic!("owned restart without marker should fail"),
            Err(error) => assert_eq!(error, "owned backend marker is missing"),
        }
    }
}
