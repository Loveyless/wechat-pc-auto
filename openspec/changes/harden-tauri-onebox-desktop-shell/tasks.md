## 1. Bootstrap contract hardening

- [x] 1.1 Replace the raw-string `/healthz` match in `desktop-shell/src-tauri/src/main.rs` with an HTTP-status plus parsed-JSON readiness check
- [x] 1.2 Define explicit managed-backend startup outcomes in the shell bootstrap layer so cold start, ready, and startup failure are distinguishable
- [x] 1.3 Update `desktop-shell/src/lib/api.ts`, `desktop-shell/src/lib/shell-types.ts`, and `desktop-shell/src/hooks/use-desktop-shell.ts` to reflect the new startup-state semantics without misusing reconnect state

## 2. Shell lifecycle and single-instance behavior

- [x] 2.1 Refactor `desktop-shell/src-tauri/src/main.rs` into smaller bootstrap-focused modules while preserving backend mutex / marker reuse behaviour
- [x] 2.2 Add shell single-instance handling so a second launch activates the existing window instead of creating another shell window
- [x] 2.3 Verify second-launch handling does not spawn an extra backend sidecar and still cleans child lifecycle correctly on exit

## 3. Sidecar packaging consistency

- [x] 3.1 Inventory the real backend and worker runtime dependencies, separating auto-collected imports from dynamic hidden imports
- [x] 3.2 Update `requirements.txt`, `pyproject.toml`, and `scripts/build_desktop_shell_sidecars.py` only for runtime dependencies proven necessary by the inventory
- [x] 3.3 Keep build-time dependency checks and packaged smoke checks aligned with the runtime dependency inventory

## 4. Automated verification

- [x] 4.1 Add a runnable desktop-shell frontend test command and regression coverage for startup-state and connection-handling logic
- [x] 4.2 Add Rust tests for extracted bootstrap logic where the refactor creates testable pure or isolated units
- [x] 4.3 Add a release-shell smoke flow that builds the shell, launches it, verifies `/healthz`, checks bootstrap logs, and validates second-launch reuse behavior

## 5. Documentation and release gate updates

- [x] 5.1 Update `docs/wechat-listening-pitfalls.md` and `docs/desktop-shell-build.md` to document the hardened bootstrap contract, startup states, single-instance behavior, and release verification flow
- [x] 5.2 Update `README.md` to reflect the new release expectations, rollback boundary, and development-only role of the Tk fallback
- [x] 5.3 Re-run the documented verification commands and record any environment-limited acceptance gaps before treating the hardened shell path as complete
