## Why

The repository has already switched its shipped desktop path to `listener_app/backend_main.py + desktop-shell/`, but the runtime contract and delivery boundary are still inconsistent: `/healthz` only proves that the HTTP handler is alive, CI feedback is concentrated in a single heavy Windows packaging workflow, configuration semantics are split across old and new paths, and the legacy Tk UI still occupies code, tests, docs, and build steps that no longer belong to the product boundary.  
This change is needed now because continuing to carry the Tk fallback and a fake health contract will keep producing false-green verification, duplicated config logic, and avoidable maintenance drag while the team has already fully committed to Tauri.

## What Changes

- Replace the current fixed `/healthz` payload with a structured runtime health contract that can distinguish startup, healthy, startup failure, and degraded states for the shipped desktop path.
- Align Tauri shell bootstrap and release smoke verification with that runtime health contract so shell readiness is based on real backend state instead of “HTTP is up”.
- Add a lightweight regression workflow for Python tests, frontend tests/build, and Rust tests so PR feedback is not blocked on full Windows packaging smoke.
- Introduce a single main-path configuration schema/loading contract for runtime settings and keep any temporary legacy compatibility limited to a thin adapter instead of preserving Tk semantics in the main path.
- **BREAKING** Remove the legacy Tk fallback UI, its packaging script, and its documentation/build entrypoints from the supported delivery path.
- Update repository docs so the only supported desktop UI and delivery path is the Tauri shell, with source-mode backend + desktop-shell dev retained only as a development/debug route.

## Capabilities

### New Capabilities
- `desktop-runtime-health`: structured backend health/status semantics for `/healthz`, shell readiness probing, and startup failure visibility.
- `desktop-runtime-config`: single-source configuration schema and validation rules for the shipped desktop runtime path, with legacy compatibility constrained to temporary adapters.
- `desktop-runtime-delivery`: supported desktop entrypoints, fast regression CI, release-smoke gates, and removal of legacy Tk packaging/documentation from the shipped path.

### Modified Capabilities
- None.

## Impact

- **Affected code**:
  - `listener_app/backend_main.py`
  - `listener_app/backend_runtime.py`
  - `listener_app/runtime_api.py`
  - `listener_app/sidebar_translate_listener.py`
  - `listener_app/sidebar_ui.py`
  - `listener_app/sidebar_translate_runtime.py`
  - `listener_app/sidebar_runtime_support.py`
  - `listener_app/sidebar_tts.py`
  - `listener_app/sidebar_shared.py`
  - `desktop-shell/src-tauri/src/backend_health.rs`
  - `desktop-shell/src-tauri/src/backend/bootstrap.rs`
  - `scripts/smoke_desktop_shell_release.py`
  - `scripts/build_windows_exe.ps1`
  - `.github/workflows/windows-packaging-smoke.yml`
  - `tests/`
- **Affected APIs / contracts**:
  - `/healthz`
  - runtime startup/degraded failure semantics consumed by shell bootstrap and release smoke
  - main-path configuration loading and validation ownership
  - supported desktop UI/build entrypoints after Tk removal
- **Dependencies / systems**:
  - Tauri shell bootstrap
  - local HTTP/WebSocket runtime contract
  - GitHub Actions validation tiers
  - documentation and release boundary for shipped desktop builds
