## 1. Backend config contract

- [ ] 1.1 Extract a runtime-config domain module that loads editable settings DTOs, resolves listener/provider config paths, and returns masked secret metadata for supported translate, display, and TTS fields
- [ ] 1.2 Implement validated config-save persistence for `listener.json` and provider-private TTS JSON with unknown-field preservation, atomic LF writes, and write-only secret updates
- [ ] 1.3 Extend `BackendRuntimeService` and `runtime_api.py` with full config read/save endpoints and apply-strategy metadata without changing existing runtime/session endpoint semantics

## 2. Desktop shell settings flow

- [ ] 2.1 Extend the desktop-shell API client and shell state hook to hydrate settings DTOs, track dirty/save/error/apply state, and keep runtime `tts-auto-read` separate from persisted defaults
- [ ] 2.2 Add a desktop-shell settings entry and settings workspace for supported translate/display fields plus provider-specific forms for `windows_system`, `doubao`, and `tencent_cloud`
- [ ] 2.3 Add frontend regression coverage for settings hydration, provider branching, save success/failure, and save-only versus managed-apply CTA states

## 3. Managed apply ownership flow

- [ ] 3.1 Add Tauri backend-ownership reporting and a managed restart command that only operates on the shell-owned backend sidecar, with Rust regression coverage for owned and unowned paths
- [ ] 3.2 Wire the desktop-shell save-and-apply flow to the Tauri managed restart path and ensure reconnect plus health recovery works without closing the main window

## 4. Documentation and verification

- [ ] 4.1 Update `config/listener.md` and `docs/wechat-listening-pitfalls.md` for the new config DTO, write-only secret handling, and save/apply behavior
- [ ] 4.2 Run Python, frontend, Rust, build, and managed/unmanaged manual verification for the full settings flow
