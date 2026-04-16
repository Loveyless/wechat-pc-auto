## Why

The desktop settings flow already owns persisted config editing, but the translate contract is still pinned to a top-level `deeplx_url` special case and TTS path selection still hangs off one drifting `tts.config_path`. That asymmetry blocks provider expansion, keeps old compatibility debt alive in the wrong layer, and makes the GUI contract harder to evolve without breaking startup loading or file-boundary persistence.

## What Changes

- Modify the runtime config schema to read provider-aware translate branches and per-provider TTS `config_path` maps while keeping backward-compatible reads for legacy `translate.deeplx_url(_env)` and legacy `tts.config_path`.
- Modify the config API contract so `GET /api/config` returns provider-aware translate/TTS DTOs with current editable secret values and `PUT /api/config` accepts `secret_updates.translate.<provider>` plus new TTS path-map writes.
- Modify the desktop settings workspace so translate provider branches cover `deeplx`, `openai_compatible`, and `passthrough`, while the first screen keeps only core TTS fields and pushes secondary tuning into advanced sections.
- Add regression coverage and docs updates for the new config shape, direct-input secret handling, compatibility reads, and provider-specific validation rules.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `desktop-runtime-config`: the main runtime schema now reads provider-aware translate config and per-provider TTS path maps while preserving legacy read compatibility.
- `desktop-runtime-config-api`: the config DTO and save payload now expose provider-aware translate branches, direct-value translate provider secret updates, and per-provider TTS `config_path` persistence.
- `desktop-shell-settings`: the settings workspace now renders translate provider branches and hides secondary TTS tuning behind advanced sections instead of treating all settings as first-screen peers.

## Impact

- **Affected code**:
  - `listener_app/runtime_config.py`
  - `listener_app/runtime_config_store.py`
  - `listener_app/sidebar_translate_runtime.py`
  - `listener_app/sidebar_shared.py`
  - `listener_app/backend_runtime.py`
  - `listener_app/runtime_api.py`
  - `desktop-shell/src/lib/settings-types.ts`
  - `desktop-shell/src/lib/api.ts`
  - `desktop-shell/src/hooks/use-desktop-settings.ts`
  - `desktop-shell/src/components/shell/settings-workspace.tsx`
  - `tests/test_runtime_config.py`
  - `tests/test_runtime_config_store.py`
  - `tests/test_runtime_api.py`
  - `desktop-shell/src/hooks/use-desktop-settings.test.ts`
  - `desktop-shell/src/components/shell/settings-workspace.test.tsx`
  - `config/listener.json`
  - `config/listener.md`
  - `docs/wechat-listening-pitfalls.md`
- **Affected APIs / contracts**:
  - `GET /api/config`
  - `PUT /api/config`
  - translate runtime schema under `listener.json`
  - TTS provider path selection under `listener.json`
- **Dependencies / systems**:
  - startup config loading and validation
  - desktop settings DTO/state model
  - translate provider runtime creation
