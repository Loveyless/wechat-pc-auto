## Why

The current desktop listener couples Tk rendering, runtime orchestration, and worker event handling in one Python entrypoint, which makes the UI hard to evolve and keeps the project out of a true frontend/backend split.  
This change is needed now because the next phase requires a React/Tauri desktop shell with a stable local API boundary while preserving the existing Python UIA runtime.

## What Changes

- Introduce a local Python runtime service boundary for session state, message events, translation state, TTS state, and configuration access.
- Add a local `HTTP + WebSocket` contract for frontend bootstrap, live updates, and runtime control.
- Replace the Tk sidebar as the primary UI path with a `React + Tauri + shadcn/ui` desktop shell that provides a session list and per-session message stream.
- Shift listening semantics from manually managed multi-target selection to all-session left-sidebar preview monitoring across both group and private chats.
- Redefine configuration around the new desktop architecture instead of preserving Tk-specific compatibility.
- Keep the old Tk entry only as a development rollback path until the new runtime passes acceptance; remove it from the primary UI path after cutover.

## Capabilities

### New Capabilities
- `desktop-runtime-api`: local HTTP and WebSocket runtime interface for sessions, messages, runtime state, configuration, and control.
- `session-preview-monitoring`: all-session left-sidebar preview monitoring with explicit preview-vs-full-message semantics.
- `desktop-shell-ui`: React/Tauri desktop shell for grouped sessions and per-session message rendering.

### Modified Capabilities
- None.

## Impact

- **Affected code**:
  - `listener_app/sidebar_translate_listener.py`
  - `listener_app/sidebar_runtime_support.py`
  - `listener_app/group_listener_worker.py`
  - `listener_app/sidebar_ui.py`
  - `config/listener.json`
  - `config/listener.md`
  - `README.md`
  - `docs/wechat-listening-pitfalls.md`
- **Affected APIs / contracts**:
  - New local HTTP endpoints for state, sessions, config, and runtime control
  - New WebSocket event contract for session/message/translation/tts/backend-state/error events
- **Dependencies / systems**:
  - Tauri desktop shell
  - React frontend
  - `shadcn/ui` component layer
  - Existing Python UIA worker/runtime remains the source of desktop events
