## ADDED Requirements

### Requirement: Desktop shell bootstrap SHALL manage owned backend sidecars on Apple Silicon macOS without Win32-only helpers
The system SHALL keep the current managed-backend bootstrap flow on `arm64 macOS`, including marker-based reuse, readiness probing, restart support, and exit cleanup, and SHALL NOT depend on Win32 mutexes, `taskkill`, or `.exe`-only assumptions.

#### Scenario: First shell launch starts a managed backend on macOS
- **WHEN** the desktop shell starts on Apple Silicon macOS and no healthy backend is already bound to the fixed ports
- **THEN** the shell spawns the backend sidecar, waits for `/healthz`, writes bootstrap logs and backend marker state under the managed runtime root, and does so without calling Win32-only helpers

#### Scenario: Shell exit cleans the owned backend on macOS
- **WHEN** the running shell owns the backend sidecar and the user closes the shell
- **THEN** the shell requests backend shutdown with mac-compatible process cleanup, and the backend health endpoint eventually becomes unavailable instead of leaving an owned runtime behind

### Requirement: Desktop shell SHALL keep `app_local_data_dir` as the runtime-root truth source on macOS
The system SHALL continue to derive the managed runtime root from Tauri `app_local_data_dir`, and SHALL keep config, marker, and bootstrap-log paths anchored under that root for `npm run tauri dev`, `npm run tauri build`, and release smoke verification.

#### Scenario: Managed shell starts with an empty runtime root
- **WHEN** the shell boots on macOS with no existing runtime files
- **THEN** the runtime root resolves from `app_local_data_dir`, and the backend receives that root through `WECHAT_AUTO_RUNTIME_ROOT` so its `config/` and `logs/` layout is initialized there

#### Scenario: Existing runtime root already contains marker and config state
- **WHEN** the shell restarts and the managed runtime root already contains the expected config and marker files
- **THEN** the shell reuses the same runtime-root layout instead of falling back to repository-relative or executable-relative paths

### Requirement: Desktop shell SHALL preserve single-instance shell behavior while reusing the existing managed backend
The system SHALL keep the current single-instance shell behavior on macOS: a second shell launch activates the existing window, does not create another shell window, and does not spawn an extra backend sidecar when the first shell already owns or is reusing the backend.

#### Scenario: User launches the shell a second time on macOS
- **WHEN** an existing shell window is already running and the user launches the shell again
- **THEN** the existing window is focused and the bootstrap log records a single-instance relaunch event instead of a second shell bootstrap

#### Scenario: Managed backend is already healthy during relaunch
- **WHEN** the user relaunches the shell while the first shell already has a healthy managed backend
- **THEN** the relaunch path preserves backend reuse semantics and no additional backend sidecar spawn is recorded
