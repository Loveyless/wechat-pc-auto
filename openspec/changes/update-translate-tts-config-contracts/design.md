## Context

The supported desktop runtime already has one shipped config owner in `listener_app/runtime_config.py`, one save path in `listener_app/runtime_config_store.py`, and one desktop settings workflow in `desktop-shell/`. The problem is that translate and TTS did not converge on the same contract shape:

- translate runtime still treats `deeplx_url` and `translate.timeout_seconds` as top-level special cases
- `GET /api/config` and `PUT /api/config` still expose translate secret handling as `translate.deeplx_url`
- TTS provider selection already uses provider branches in the DTO, but listener persistence still writes only one drifting `tts.config_path`
- the settings first screen still mixes core provider selection with secondary TTS tuning knobs

This change is cross-cutting because it touches startup loading, save-time validation, runtime translator creation, DTO typing, and settings UI composition. It also has compatibility pressure: existing runtime roots may still contain old `translate.deeplx_url(_env)` and old single-path TTS config, and those existing files must keep loading.

## Goals / Non-Goals

**Goals:**
- Convert translate config to a provider-aware structure with shared fields plus `translate.providers.<provider>` branches.
- Support `openai_compatible` as a first-class translate provider with `base_url`, `model`, `api_key`, and `timeout_seconds`.
- Persist TTS provider path selection as `tts.providers.<provider>.config_path` without losing inactive provider paths.
- Keep compatibility reads for legacy `translate.deeplx_url(_env)`, legacy `translate.timeout_seconds`, and legacy `tts.config_path`, but write only the new structure after save.
- Keep secrets write-only in the config API and keep file-boundary persistence plus atomic LF writes.
- Keep the settings first screen focused on core translate/TTS controls while moving secondary TTS tuning into advanced sections.

**Non-Goals:**
- Changing `/healthz`, `/api/runtime`, `/api/sessions`, or WebSocket contracts
- Adding `.env.local` editing for translate secrets
- Adding extra translate providers beyond `deeplx`, `openai_compatible`, and `passthrough`
- Changing TTS provider-private JSON boundaries or moving cloud TTS secrets into `listener.json`
- Adding in-process hot reload for translator or TTS runtime objects

## Decisions

### Decision: Make translate provider-aware in `listener.json`, but keep startup compatibility reads

The new persisted structure will keep shared translate fields at the top level:
- `enabled`
- `provider`
- `source_lang`
- `target_lang`

Provider-specific fields move under `translate.providers`:
- `translate.providers.deeplx.{deeplx_url, deeplx_url_env, timeout_seconds}`
- `translate.providers.openai_compatible.{base_url, model, api_key, timeout_seconds}`
- `translate.providers.passthrough` remains empty

Startup loading will accept both:
- new provider-aware branches
- old `translate.deeplx_url`, `translate.deeplx_url_env`, and top-level `translate.timeout_seconds`

Save paths will write only the new provider-aware shape.

**Alternatives considered**
- **Keep `translate.timeout_seconds` top-level forever**: rejected because `openai_compatible` needs provider-specific required fields and timeout belongs with the provider transport semantics.
- **Create a separate translate provider JSON file like TTS**: rejected because translate config already belongs to shared listener config and does not need another persistence boundary.

### Decision: Extend runtime translate loading with explicit active-provider fields instead of a generic untyped blob

`RuntimeTranslateConfig` will keep shared fields plus explicit resolved fields for the active provider, including:
- `deeplx_url`
- `openai_base_url`
- `openai_model`
- `openai_api_key`
- `timeout_seconds`

That keeps startup validation and `create_translator()` simple and avoids pushing raw config parsing deeper into runtime orchestration.

**Alternatives considered**
- **Pass an untyped provider blob into `create_translator()`**: rejected because it would duplicate validation between loader and runtime creation and make test failures noisier.
- **Model every provider through a new class hierarchy in `runtime_config.py`**: rejected because the repo currently uses compact dataclasses and this change does not need a larger object model.

### Decision: Keep config API secrets write-only, and forbid `api_key_env` for `openai_compatible`

`GET /api/config` will return provider-aware translate secret metadata only. `PUT /api/config` will accept:
- `secret_updates.translate.deeplx.deeplx_url` with `keep/direct/env/clear`
- `secret_updates.translate.openai_compatible.api_key` with `keep/direct/clear`

`openai_compatible` will not support env indirection through the GUI contract. If operators want env-based behavior later, that should be a separate change with explicit UX and compatibility rules.

**Alternatives considered**
- **Allow `api_key_env` immediately for symmetry**: rejected because the requirement explicitly disallows it, and pretending symmetry exists would silently expand the secret contract.
- **Return masked raw secret strings to simplify the form**: rejected because it weakens the current write-only secret boundary.

### Decision: Persist TTS path selection as a per-provider map and resolve legacy single-path reads as fallback

The new listener structure will keep `tts.provider` and add:
- `tts.providers.doubao.config_path`
- `tts.providers.tencent_cloud.config_path`

`windows_system` keeps no `config_path`. Startup loading will resolve provider-private files from the per-provider map first, then fall back to legacy `tts.config_path` when the active provider lacks a new path entry. Save paths will write only the per-provider map and remove the single legacy `config_path`.

**Alternatives considered**
- **Keep writing both old and new TTS path fields for a while**: rejected because dual-write prolongs ambiguity and makes rollback harder to reason about.
- **Move provider-private TTS payloads back into `listener.json`**: rejected because it breaks the existing persistence boundary and contradicts shipped behavior.

### Decision: Keep the settings first screen strict about core fields and hide secondary TTS tuning in advanced sections

The settings workspace will keep translate provider selection, credentials, and TTS provider/path fields visible at the top level. Secondary TTS tuning such as `speech_rate`, `loudness_rate`, `speed`, `volume`, and `request_timeout_seconds` will move behind provider-specific advanced sections instead of competing with core setup fields.

**Alternatives considered**
- **Leave all TTS fields flat on the first screen**: rejected because the current layout buries the real setup path under secondary tuning.
- **Remove secondary tuning entirely**: rejected because those fields already exist and are still needed for non-default provider setups.

## Risks / Trade-offs

- **[Legacy runtime roots load but save into a shape older code no longer writes]** -> keep compatibility reads in `runtime_config.py`, document one-way migration, and cover old-file-startup plus new-file-save tests.
- **[Translate provider validation diverges between startup and save]** -> route both through shared provider validators and add focused invalid-payload tests for `deeplx` and `openai_compatible`.
- **[Settings UI grows more state branches and becomes brittle]** -> keep provider typing explicit in `settings-types.ts` and add regression tests for branch rendering and save payload generation.
- **[Operators expect `openai_compatible` env mode because DeepLX has one]** -> document that `api_key` is direct/clear only in this change and surface it explicitly in the settings UI copy.

## Migration Plan

1. Establish current shipped config specs as baseline and land this change’s delta artifacts.
2. Extend Python runtime config loading and config-save helpers for provider-aware translate plus per-provider TTS path maps.
3. Extend translator runtime creation for `openai_compatible`.
4. Update desktop settings types, save payload generation, and UI composition.
5. Update docs, defaults, and regression coverage.

**Rollback strategy**
- Revert the new translate provider-aware writes and TTS path-map writes together.
- Keep existing provider-private TTS JSON files untouched during rollback.
- If the new settings UI proves unstable, keep backend compatibility reads and fall back to the previous DTO/UI contract rather than deleting provider data.

## Open Questions

- None. The required `openai_compatible` field set is fixed to `base_url`, `model`, `api_key`, and `timeout_seconds`, and GUI env indirection for `api_key` is explicitly out of scope.
