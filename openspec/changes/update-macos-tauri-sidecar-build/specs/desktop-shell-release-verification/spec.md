## ADDED Requirements

### Requirement: Sidecar packaging SHALL emit target-triple-suffixed binaries for macOS without `.exe`
The system SHALL build the backend and worker sidecars using the host Rust target triple and platform extension rules, so Apple Silicon macOS installs `wechat-auto-backend-<target>` and `group_listener_worker-<target>` without `.exe`.

#### Scenario: Sidecar build runs on Apple Silicon macOS
- **WHEN** `scripts/build_desktop_shell_sidecars.py` is executed on a host whose Rust target triple is `aarch64-apple-darwin`
- **THEN** the built sidecars are installed into `desktop-shell/src-tauri/binaries/` as `wechat-auto-backend-aarch64-apple-darwin` and `group_listener_worker-aarch64-apple-darwin`

#### Scenario: Tauri resolves the built sidecars on macOS
- **WHEN** the shell build/dev flow looks up `bundle.externalBin` entries for the backend and worker sidecars
- **THEN** the installed macOS sidecar file names match Tauri's target-triple naming expectations and are discoverable without adding `.exe`

### Requirement: Release-shell smoke SHALL verify startup, relaunch, and cleanup on macOS
The system SHALL provide a mac-compatible release smoke flow that verifies release-shell startup, `/healthz` readiness, bootstrap-log observations, second-launch single-instance behavior, and owned-backend cleanup.

#### Scenario: Fresh release smoke passes on macOS
- **WHEN** the mac release smoke launches the built shell for the first time
- **THEN** `/healthz` becomes ready, bootstrap logs record a single backend sidecar spawn, and the smoke run captures the runtime-root log location it validated

#### Scenario: Release smoke validates relaunch and cleanup on macOS
- **WHEN** the mac release smoke launches the shell a second time and then closes the owned shell process
- **THEN** the smoke confirms the single-instance relaunch log entry, confirms no duplicate backend spawn occurred, and confirms the backend health endpoint becomes unavailable after cleanup

### Requirement: Desktop-shell build verification SHALL keep packaged checks aligned with the supported mac-only branch
The system SHALL keep the documented verification entry points and smoke-test defaults aligned with the supported Apple Silicon macOS branch so developers do not validate Windows-only outputs by mistake.

#### Scenario: Developer runs the documented desktop-shell release gate on the mac branch
- **WHEN** a maintainer follows the documented build and smoke commands for the desktop shell
- **THEN** the commands, runtime-root expectations, and artifact names match the Apple Silicon macOS branch instead of `%LOCALAPPDATA%`, `.exe`, `msi`, or `nsis`
