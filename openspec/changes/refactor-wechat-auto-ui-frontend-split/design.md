## Context

The repository currently runs as a Python desktop application whose main entrypoint (`listener_app/sidebar_translate_listener.py`) coordinates configuration, runtime supervision, translation flow, event dispatch, and Tk rendering.  
The current UI (`listener_app/sidebar_ui.py`) is Tk-based. Worker events come from `listener_app/group_listener_worker.py` via stdout JSON and are consumed by runtime helpers in `listener_app/sidebar_runtime_support.py`.  
The repository documentation already states that listening and UI must be separated, and current limitations explicitly say the listener reads left-sidebar session previews rather than full chat history.

## Goals / Non-Goals

**Goals:**
- Split the desktop application into a Python local backend and a React/Tauri frontend.
- Define a stable local `HTTP + WebSocket` contract for sessions, messages, runtime state, translation state, and TTS state.
- Replace the Tk primary UI path with a Tauri desktop shell using `shadcn/ui`.
- Support all-session left-sidebar preview monitoring across group and private chats.
- Keep real-time translation display and TTS autoplay semantics.

**Non-Goals:**
- Rewriting UIA logic in Rust
- Cross-platform support
- Changing the core translation provider or TTS provider strategy
- Solving packaging/distribution in this phase
- Preserving old Tk configuration compatibility
- Keeping Tk as a long-lived shipped fallback UI

## Decisions

### Decision: Keep Python as the backend runtime, but service-ify it behind local HTTP + WebSocket

The Python runtime already owns UIA, worker management, translation, and TTS orchestration. Replacing that in Phase 1 would expand scope too far.  
Instead, the change will extract a Tk-independent local backend service and expose:

- HTTP for bootstrap/config/control
- WebSocket for live events

**Alternatives considered**
- **Tauri <-> Python stdout/IPC directly**: rejected because it couples the frontend to process internals and makes observability, tooling, and future separation worse.
- **Rewrite backend to Rust now**: rejected because Phase 1 is about architecture split and UI replacement, not backend language migration.

### Decision: Treat left-sidebar preview monitoring as a first-class product contract

Phase 1 explicitly accepts preview-level monitoring rather than promising full chat-body capture.  
The backend must therefore distinguish preview-derived events from full-message events and must not imply complete-message fidelity where the current WeChat UIA path cannot guarantee it.

**Alternatives considered**
- **Promise full-body monitoring in Phase 1**: rejected because current repository facts and docs explicitly describe preview-only limitations.

### Decision: Scope the first frontend to session list + per-session message stream only

The first frontend must ship only the two required views:

- session list
- per-session message stream

This keeps the cutover focused and prevents the UI rewrite from being blocked by logs, trays, or broad settings panels.

**Alternatives considered**
- **Include full settings/logging/tray in Phase 1**: rejected because it dilutes the architecture split and delays the main UI replacement.

### Decision: Allow configuration redesign

The new desktop split is allowed to redefine configuration shape rather than dragging Tk-specific compatibility forward.  
Documentation must be updated as part of cutover.

**Alternatives considered**
- **Keep full backward compatibility for config**: rejected because it preserves legacy coupling and increases implementation friction.

### Decision: Keep old Tk only as a development rollback path until acceptance passes

Tk is not a long-term shipped fallback.  
However, during migration and validation, the old Tk entry remains available so the team can compare behaviour and revert locally if the new runtime fails acceptance.

**Alternatives considered**
- **Immediate hard delete of Tk path before new runtime passes acceptance**: rejected because it removes the safest rollback point during the cutover window.

## Risks / Trade-offs

- **Preview monitoring is not full-message monitoring** → Distinguish preview events from full-message events in the backend model and docs.
- **No packaging/distribution work in Phase 1** → Accept that the distribution pain remains and keep it out of this change scope.
- **Removing Tk as the primary UI path raises cutover risk** → Require acceptance criteria and keep Tk available only during development rollback.
- **Config redesign breaks old usage** → Ship explicit migration docs rather than silent compatibility hacks.

## Migration Plan

1. Freeze the current runtime behaviour and extract the domain model for sessions, messages, runtime state, translation state, and TTS state.
2. Introduce a Tk-independent backend service entrypoint and keep the old Tk path callable during migration.
3. Add local HTTP bootstrap endpoints and WebSocket live event delivery.
4. Build the Tauri/React frontend with session list and per-session message stream views.
5. Validate the new runtime against the acceptance criteria while the old Tk entry remains available for development rollback.
6. Switch the primary desktop UI path to Tauri + Python backend.
7. Remove Tk from the primary run path and update docs/config references.

**Rollback strategy**
- If the new runtime fails acceptance, do not flip the primary UI path; continue using the old Tk entry during development and revert the branch if needed.
- Do not ship a long-term dual-UI runtime.

## Open Questions

- None. Phase 1 accepts preview-level all-session monitoring and uses Tk only as a temporary development rollback path before cutover.
