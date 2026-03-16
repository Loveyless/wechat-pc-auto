## Context

The supported desktop runtime still loads configuration once at backend startup through `load_runtime_config()` and `load_backend_settings()`, while the current local API exposes only a partial `/api/config` snapshot. The desktop shell does not consume that snapshot, has no settings entry, and only mutates the runtime-only `tts-auto-read` toggle.  
At the same time, runtime configuration is intentionally split across `listener.json` and provider-private JSON files, secrets may come from direct values or `*_env` indirection, and the Tauri shell already owns managed backend bootstrap plus health waiting. Any GUI configuration flow that ignores those boundaries will either leak secrets, overwrite unknown fields, or kill the wrong backend process.

## Goals / Non-Goals

**Goals:**
- Expose a complete, safe configuration DTO for the supported editable fields in the desktop runtime path.
- Keep `listener.json` and provider-private config files as separate persistence boundaries while preserving unknown fields and writing JSON atomically with LF.
- Support write-only secret updates and safe read masking so the frontend can show configuration state without receiving raw secrets back.
- Add a desktop-shell settings experience that covers supported translate, display, and TTS provider configuration and clearly distinguishes runtime-only toggles from persisted defaults.
- Allow “save and apply” only when the shell owns the backend sidecar and can restart it without touching external or reused backends.

**Non-Goals:**
- In-process translator or TTS hot reload inside the Python backend
- A general `.env.local` editor
- Moving provider-private TTS fields back into `listener.json`
- Changing `/healthz`, `/api/runtime`, `/api/sessions`, or `/events` semantics
- Folding the separate desktop-shell visual-system change into this change

## Decisions

### Decision: Introduce a dedicated runtime-config domain layer on the Python side

Configuration read/write logic will move behind a dedicated runtime-config domain module instead of expanding `backend_runtime.py` further. That module will own:
- safe response DTO shaping for `GET /api/config`
- request parsing and validation for config save requests
- listener/provider file resolution
- unknown-field preservation and atomic JSON writes
- write-only secret handling metadata

`load_runtime_config()` remains the startup schema owner for runtime behaviour, but the new domain layer will reuse the same validation rules and provider helpers so save-time validation stays fail-fast and consistent with startup behaviour.

**Alternatives considered**
- **Keep save logic inside `backend_runtime.py`**: rejected because it would turn an already cross-cutting orchestration file into a config serializer, validator, and persistence bucket.
- **Let the frontend write JSON files directly through Tauri FS APIs**: rejected because it would duplicate schema logic, bypass Python-side validation, and make non-Tauri/dev flows inconsistent.

### Decision: Model config exchange as a safe DTO plus write-only secret patch semantics

`GET /api/config` will return a complete editable DTO for supported fields, but secret-like values will be represented only as metadata such as `configured`, `source`, and optional `envKey`. `PUT /api/config` will accept full non-secret settings plus write-only secret updates for direct values or env indirection.  
Persistence will keep two boundaries:
- `listener.json` for shared runtime fields and provider selection
- provider-private JSON for provider-specific TTS fields

Unknown fields from both files will be preserved by loading current payloads, overlaying supported edited fields, and writing the merged result atomically.

**Alternatives considered**
- **Return raw secrets back to the frontend after save**: rejected because it creates unnecessary exposure and breaks the plan’s write-only secret constraint.
- **Store all settings in one normalized API-only schema and regenerate files**: rejected because it would destroy current compatibility and make rollback harder.

### Decision: Keep apply as a two-phase save-then-restart flow owned by the shell, not the backend

The backend API will validate and persist configuration, then report whether runtime apply is available for the current connection. Actual managed apply will stay in Tauri because only the shell knows whether the connected backend is the child process it spawned.  
The flow is:
1. frontend submits save request to backend
2. backend persists config files and returns `apply_strategy`
3. if strategy is managed, frontend invokes a Tauri command that restarts only the owned backend sidecar
4. frontend reconnects through the existing bootstrap and WebSocket lifecycle

Unmanaged or development connections will never receive a backend-driven kill path; they only surface “saved, restart backend manually”.

**Alternatives considered**
- **Let Python backend restart itself on save**: rejected because it cannot prove shell ownership and would risk killing external or reused backends.
- **Always require full app restart even for managed sidecars**: rejected because Tauri already owns sidecar bootstrap, and not using that capability would leave avoidable operator friction on the main packaged path.

### Decision: Separate persisted defaults from runtime-only toggles in the shell state model

The header auto-read toggle will stay a runtime action backed by the existing `/api/runtime/tts-auto-read` contract. The settings screen will edit the persisted startup default `display.tts_auto_read_active_chat` as a separate field. The frontend state model must keep these values separate so runtime interaction does not dirty persisted settings implicitly.

**Alternatives considered**
- **Bind the header toggle directly to persisted config**: rejected because it would silently rewrite files during normal runtime interaction and blur “effective now” versus “default on next start”.
- **Duplicate the runtime toggle inside settings only**: rejected because it would remove a useful quick action from the main shell flow.

## Risks / Trade-offs

- **[Secret metadata or masking is inconsistent across providers]** -> Reuse provider-specific helpers and add backend tests for direct secret, env-backed secret, and write-only update paths.
- **[Unknown fields or config path semantics regress]** -> Always merge against current file payloads resolved from the runtime root and cover listener/provider file writes with focused tests.
- **[Managed apply restarts the wrong backend]** -> Gate restart behind Tauri-owned marker validation and expose unmanaged connections as save-only.
- **[Frontend state becomes muddled between persisted config and runtime state]** -> Keep settings DTO state isolated from `useDesktopShell()` runtime toggles and add tests for dirty-state and CTA branching.
- **[Cross-stack rollout becomes brittle]** -> Land the flow in layers: backend contract first, frontend settings flow second, Tauri managed apply last, with docs and regression updates before sign-off.

## Migration Plan

1. Add the Python runtime-config domain layer, config DTO endpoints, validation, and persistence tests.
2. Add desktop-shell settings API client/state handling and settings UI for supported fields and provider branches.
3. Add Tauri managed-apply command plus backend bootstrap restart guards and reconnect flow.
4. Update operator documentation and run Python, frontend, Rust, build, and manual managed/unmanaged verification.

**Rollback strategy**
- Revert the settings UI, config API write paths, and Tauri managed-apply command together.
- Keep file schema compatibility unchanged so rollback does not require data migration.
- If managed apply proves unstable, keep save-only semantics and disable the apply CTA without removing the config DTO/save path.

## Open Questions

- None. The plan already fixes the first-stage boundary: save is mandatory, apply is conditional, and in-process hot reload remains out of scope.
