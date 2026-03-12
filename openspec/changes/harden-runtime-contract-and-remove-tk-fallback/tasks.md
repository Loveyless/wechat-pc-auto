## 1. Runtime health contract

- [x] 1.1 Add a structured backend health model for `/healthz` in the Python runtime path, including `starting`, `ok`, `startup_failed`, and `degraded`
- [x] 1.2 Change the backend entrypoint/startup flow so startup failure is observable through the health contract instead of disappearing before the HTTP layer exists
- [x] 1.3 Extend Python API/runtime tests to cover structured health responses and startup-failure visibility

## 2. Shell bootstrap and release smoke alignment

- [x] 2.1 Update Tauri-side health parsing and bootstrap readiness checks to consume the structured `/healthz` contract
- [x] 2.2 Update release smoke validation to distinguish non-ready health states from healthy runtime availability and fail with actionable diagnostics
- [x] 2.3 Add or update Rust/bootstrap tests for the new readiness semantics

## 3. Fast regression gate and config schema ownership

- [x] 3.1 Add a lightweight CI workflow for Python tests, desktop-shell frontend tests/build, and Rust tests without packaged Windows smoke
- [ ] 3.2 Extract a single authoritative runtime configuration schema/loading module for the supported desktop path
- [ ] 3.3 Migrate the surviving desktop runtime code to the shared config schema and keep any temporary legacy compatibility behind a thin adapter only

## 4. Test separation and Tk removal

- [ ] 4.1 Split `tests/test_sidebar_listener_helpers.py` into shared-runtime coverage versus Tk-specific UI coverage
- [ ] 4.2 Remove Tk-only UI entrypoints and implementation files while preserving shared runtime/translate/TTS/helper modules still used by `backend_main.py + desktop-shell/`
- [ ] 4.3 Remove the legacy Tk packaging script and delete Tk references from CI so the shipped desktop gate no longer exercises the legacy path

## 5. Documentation and acceptance

- [ ] 5.1 Update README, `config/listener.md`, and `docs/wechat-listening-pitfalls.md` so the supported desktop path, config contract, and rollback wording match the post-Tk boundary
- [ ] 5.2 Remove legacy Tk packaging documentation and replace it with Tauri-only delivery guidance where needed
- [ ] 5.3 Re-run the documented fast checks and release smoke commands, then record any environment-limited acceptance gaps before treating the change as complete
