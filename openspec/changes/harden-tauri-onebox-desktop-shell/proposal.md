## Why

The current Tauri desktop shell is already able to build and launch the Python sidecars, but core delivery paths are still fragile: backend readiness is misdetected by a brittle string match, startup state is exposed as reconnect noise instead of a real cold-start phase, and shell lifecycle rules are not yet hardened for single-instance delivery.  
This change is needed now because the repository has already cut over to `backend_main.py + desktop-shell/` as the main path, so startup reliability, sidecar packaging consistency, and release verification can no longer be treated as follow-up polish.

## What Changes

- Replace the current backend ready check with a stable shell-to-backend bootstrap contract based on HTTP status and parsed `/healthz` JSON instead of raw string matching.
- Define an explicit desktop-shell startup state model so the frontend can distinguish backend starting, backend ready, and startup failure without misreporting cold start as reconnect failure.
- Harden the desktop shell as single-instance behavior so the second launch activates the existing window instead of creating another shell against the same backend.
- Align sidecar packaging with the real runtime dependency and hidden-import set instead of stale or environment-dependent assumptions.
- Add automated verification for frontend connection logic, Rust bootstrap logic, and release-shell smoke coverage so `npm run tauri build` is not the only gate.
- Keep rollback and degradation bounded to the existing `backend_main.py + desktop-shell/` main path; the old Tk entry remains development-only fallback for diagnosis, not a shipped rollback target.

## Capabilities

### New Capabilities
- `desktop-shell-bootstrap`: stable managed-backend bootstrap, readiness probing, startup state transitions, backend reuse, and single-instance activation behavior for the Tauri shell.
- `desktop-shell-release-verification`: sidecar dependency consistency checks, build-time verification, automated frontend/bootstrap tests, and release smoke validation for the desktop-shell delivery path.

### Modified Capabilities
- None.

## Impact

- **Affected code**:
  - `desktop-shell/src-tauri/src/main.rs`
  - `desktop-shell/src-tauri/Cargo.toml`
  - `desktop-shell/src/lib/api.ts`
  - `desktop-shell/src/hooks/use-desktop-shell.ts`
  - `desktop-shell/src/lib/shell-types.ts`
  - `desktop-shell/package.json`
  - `scripts/build_desktop_shell_sidecars.py`
  - `requirements.txt`
  - `pyproject.toml`
  - `tests/`
  - `docs/wechat-listening-pitfalls.md`
  - `docs/desktop-shell-build.md`
  - `README.md`
- **Affected APIs / contracts**:
  - `/healthz` readiness contract as consumed by the shell bootstrap
  - frontend connection-state semantics exposed by the shell runtime
  - second-launch shell activation behavior under single-instance mode
- **Dependencies / systems**:
  - Tauri shell bootstrap and Rust plugins
  - PyInstaller sidecar build flow
  - local HTTP/WebSocket runtime path
  - release build and smoke-test workflow
