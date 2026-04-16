## Why

The desktop shell now owns the main UI path, but runtime configuration still depends on hand-editing JSON files and guessing whether a restart is required.  
That gap is already causing a correctness problem: a settings page without a backed contract would only create fake configuration that looks editable but does not safely save, validate, or apply.

## What Changes

- Add a local runtime-config API that exposes a complete, safe, editable DTO for the supported desktop-shell settings, validates writes, preserves unknown fields, and writes runtime config files atomically.
- Add a desktop-shell settings entry and settings screen for supported translation, display, and TTS configuration, including all currently supported TTS providers: `windows_system`, `doubao`, `less_tts`, and `tencent_cloud`.
- Add explicit save/apply semantics: unmanaged or development connections stay on `save only + manual restart required`, while Tauri-managed connections may restart only the backend sidecar owned by the current shell instance after saving.
- Keep runtime-only toggles separate from persisted defaults so the header auto-read toggle does not silently rewrite the configured startup default.
- Add regression coverage and documentation updates for config DTO direct-value echo, direct-input secret handling, provider-specific forms, managed apply gating, and the new operator workflow.

## Capabilities

### New Capabilities
- `desktop-runtime-config-api`: safe read, validate, and save contracts for editable backend runtime configuration, including direct-value secret echo for continued editing and atomic persistence boundaries.
- `desktop-shell-settings`: desktop-shell settings entry, editable forms, save feedback, and apply-state messaging for supported translate/display/TTS configuration.
- `desktop-managed-backend-apply`: managed backend restart flow that only applies to a shell-owned sidecar and reconnects the desktop shell after a successful save.

### Modified Capabilities
- None.

## Impact

- **Affected code**:
  - `listener_app/runtime_api.py`
  - `listener_app/backend_runtime.py`
  - `listener_app/runtime_config.py`
  - `listener_app/sidebar_shared.py`
  - `listener_app/sidebar_tts.py`
  - `desktop-shell/src/lib/api.ts`
  - `desktop-shell/src/hooks/use-desktop-shell.ts`
  - `desktop-shell/src/components/shell/**`
  - `desktop-shell/src-tauri/src/main.rs`
  - `desktop-shell/src-tauri/src/backend/**`
  - `config/listener.md`
  - `docs/wechat-listening-pitfalls.md`
- **Affected APIs / contracts**:
  - `GET /api/config`
  - new config save/apply API surface in `listener_app/runtime_api.py`
  - new Tauri command(s) for managed backend apply
- **Dependencies / systems**:
  - runtime config loader and validation path
  - desktop-shell HTTP/WebSocket client flow
  - Tauri-managed backend bootstrap ownership and health waiting
