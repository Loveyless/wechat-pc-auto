## Why

The branch target is already Apple Silicon macOS, but the shipped TTS default, system voice runtime, and related docs still point at Windows-only behavior such as `windows_system`, `System.Speech`, `winsound`, and `winmm`. That mismatch now blocks fresh installs, makes the settings contract inaccurate for the supported branch, and risks sending existing runtime configs into a broken playback path.

## What Changes

- Modify the shipped TTS default from `windows_system` to `macos_system` for repository defaults and fresh runtime roots so the supported branch can start without cloud credentials.
- Modify the backend TTS runtime so system playback and cloud-provider playback use mac-compatible execution paths while preserving the existing auto-read behavior for the active chat.
- Modify the runtime config and config API surfaces so provider enums, defaults, and compatibility handling reflect the mac-only branch without redesigning `GET /api/config` or `PUT /api/config`.
- Modify the desktop settings workspace and repository docs so supported TTS provider choices, defaults, and migration guidance match the shipped macOS behavior.
- Add explicit compatibility handling for persisted `windows_system` values so old runtime roots surface a defined migration path instead of silently entering a Windows-only failure mode.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `desktop-runtime-config`: TTS provider defaults, compatibility handling, and shipped runtime behavior change from Windows-only system speech to macOS system speech for the supported branch.
- `desktop-runtime-config-api`: the editable config DTO and save semantics continue to use the existing contract shape, but the supported TTS provider enum, default value, and compatibility behavior now reflect `macos_system`.
- `desktop-shell-settings`: the settings workspace continues to cover all supported TTS providers, but the system-provider branch, default selection, and migration messaging now match the mac-only branch instead of Windows-only behavior.

## Impact

- **Affected code**:
  - `listener_app/sidebar_tts.py`
  - `listener_app/runtime_config.py`
  - `listener_app/runtime_config_store.py`
  - `listener_app/runtime_api.py`
  - `listener_app/backend_runtime.py`
  - `listener_app/backend_main.py`
  - `desktop-shell/src/lib/settings-types.ts`
  - `desktop-shell/src/components/shell/settings-workspace.tsx`
  - `desktop-shell/src/components/shell/settings-workspace.test.tsx`
  - `tests/test_runtime_config.py`
  - `tests/test_runtime_config_store.py`
  - `tests/test_runtime_api.py`
  - `config/listener.json`
  - `config/listener.md`
  - `docs/wechat-listening-pitfalls.md`
- **Affected APIs / contracts**:
  - `GET /api/config`
  - `PUT /api/config`
  - TTS provider defaults and compatibility behavior under `listener.json`
- **Dependencies / systems**:
  - macOS system speech playback
  - desktop settings DTO and provider branches
  - TTS dependency checks and runtime auto-read flow
