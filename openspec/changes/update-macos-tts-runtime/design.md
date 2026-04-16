## Context

The supported branch is Apple Silicon macOS only, but the TTS runtime and config surface still expose Windows-only behavior in multiple layers:

- `listener_app/sidebar_tts.py` still treats `windows_system` as the only built-in system provider and routes cloud playback through Windows playback helpers.
- `listener_app/runtime_config.py` and `listener_app/runtime_config_store.py` still normalize and serialize `windows_system` as a supported provider in the runtime config and settings DTO.
- `desktop-shell/src/lib/settings-types.ts` and `desktop-shell/src/components/shell/settings-workspace.tsx` still make `windows_system` a selectable settings branch.
- `config/listener.json`, `config/listener.md`, and `docs/wechat-listening-pitfalls.md` still describe `windows_system` as the shipped default even though the branch no longer supports Windows.

The existing config/save/settings changes already define the authoritative config owner and DTO/save boundaries, so this change must stay inside those contracts instead of inventing a second configuration path.

## Goals / Non-Goals

**Goals:**

- Make `macos_system` the shipped default system TTS provider for repository defaults and fresh runtime roots.
- Keep auto-read behavior working on macOS for both system speech and cloud-provider playback.
- Preserve the current `GET /api/config` and `PUT /api/config` save boundaries while updating provider enums, defaults, and compatibility behavior.
- Give legacy `windows_system` runtime roots a defined migration path that does not fall back into Windows-only playback code.

**Non-Goals:**

- Redesign the config DTO shape, secret model, or provider-private file ownership introduced by other active changes.
- Add new product capabilities such as voice download, speech caching, or richer TTS controls.
- Preserve `windows_system` as a selectable supported provider for the mac-only branch.
- Introduce new Python or frontend dependencies purely for this migration.

## Decisions

### 1. `macos_system` becomes the only supported built-in system provider

The backend runtime, config snapshot, and desktop settings will treat `macos_system` as the built-in system provider for the supported branch. `windows_system` will become a legacy load-only value:

- runtime loading accepts persisted `windows_system` and immediately normalizes it to the macOS system path
- config snapshots and save payloads expose `macos_system`, not `windows_system`
- settings no longer offer `windows_system` as a selectable branch

This keeps old runtime roots bootable without preserving a Windows-only branch as an advertised capability.

**Alternatives considered**

- Keep `windows_system` selectable: rejected because it advertises an unsupported branch fact and keeps invalid settings UI alive.
- Hard-fail on legacy `windows_system`: rejected because it would break existing runtime roots before the user can reach settings and resave.

### 2. System speech uses `say`; cloud playback uses a shared macOS audio command path

The new system-provider runtime will use the macOS `say` command and keep the existing queued `speak_async()` contract so `BackendRuntimeService` does not need a new TTS interface. Cloud providers keep their current synthesis logic, but audio playback moves off Windows-specific helpers and onto a macOS command path based on temporary files plus `afplay`.

This keeps the change dependency-free, works for both `wav` and `mp3`, and avoids pulling `PyObjC`/`NSSpeechSynthesizer` into the first migration step.

**Alternatives considered**

- `NSSpeechSynthesizer`: rejected for the first pass because it adds a larger API surface and more lifecycle/testing work than needed for the acceptance target.
- Python-native audio libraries: rejected because they would add new runtime dependencies and packaging work.

### 3. Config and settings contracts stay structurally unchanged

The change will reuse the current authoritative schema and file-boundary persistence:

- `listener.json` continues to own shared `tts.provider` and `tts.providers.<provider>.config_path`
- cloud-provider private fields remain in provider JSON files
- `GET /api/config` / `PUT /api/config` keep the existing DTO/save structure

Only the TTS provider enum, default value, snapshot branches, and compatibility normalization change. Saving after a legacy load persists `macos_system`, which makes the migration self-healing without adding a separate migration command.

**Alternatives considered**

- Add a second migration API or standalone rewrite step: rejected because it duplicates the config contract already being standardized elsewhere.
- Preserve `windows_system` in DTOs as a hidden compatibility branch: rejected because it leaks unsupported behavior back into the editable surface.

### 4. Compatibility is surfaced through runtime behavior and docs, not a new settings protocol

This change will not add a new warning channel to `/api/config`. Instead, compatibility is explicit through:

- startup/runtime log text that states legacy `windows_system` was normalized for macOS
- docs that describe `windows_system` as legacy input only
- regression coverage that proves legacy configs boot and resave to `macos_system`

This keeps the settings/API contract stable while still avoiding silent fallback to Windows-only code.

## Risks / Trade-offs

- `[Process control is coarser with say/afplay]` → keep the existing async queue interface, document that first-pass mac playback optimizes for correctness over advanced interruption controls, and leave deeper control for a later `NSSpeechSynthesizer` upgrade if needed.
- `[Legacy config normalization could be missed in some code paths]` → centralize normalization in the existing provider loader/snapshot path and add regression tests for load, save, API snapshot, and runtime creation.
- `[Concurrent OpenSpec changes already touch config/settings contracts]` → restrict this change to provider/default/runtime facts and avoid reworking DTO shape, save strategy, or settings layout ownership.

## Migration Plan

1. Update runtime defaults, provider normalization, and TTS player creation so fresh and legacy runtime roots both resolve to mac-compatible behavior.
2. Update config snapshot/save handling and settings types/UI so `macos_system` is the supported system-provider branch everywhere user-editable data is exposed.
3. Update repository defaults and docs so shipped samples match the supported branch.
4. Run targeted Python/frontend regression checks plus the existing TTS dependency check command. If full end-to-end speech verification is environment-limited, record manual verification steps instead of widening scope.

## Open Questions

- The first pass will use `say` and `afplay`; if later testing shows the current interruption semantics are insufficient, the follow-up path is to replace only the local playback backend with `NSSpeechSynthesizer` or a richer macOS-native wrapper without reopening the config contract.
