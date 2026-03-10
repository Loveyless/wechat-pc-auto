## 1. Runtime boundary extraction

- [x] 1.1 Extract Tk-independent session, message, runtime-state, translation-state, and TTS-state models from the current Python entry path
- [x] 1.2 Define explicit preview-event vs full-message-event semantics in the backend domain model
- [x] 1.3 Introduce a backend runtime entrypoint that can supervise the listener flow without constructing the legacy Tk UI

## 2. Local API and event transport

- [x] 2.1 Add local HTTP endpoints for runtime snapshot, sessions, config, and explicit runtime control
- [x] 2.2 Add a local WebSocket event stream for session, message, translation, TTS, backend-state, and error events
- [x] 2.3 Add contract-focused smoke tests or fixtures for the HTTP and WebSocket payloads

## 3. Session monitoring model shift

- [x] 3.1 Refactor the current target-based monitoring path into all-session left-sidebar preview monitoring across group and private chats
- [x] 3.2 Preserve translation output and TTS autoplay semantics in the new event flow
- [x] 3.3 Keep preview-only limitations explicit in runtime state, API payloads, and docs

## 4. Tauri frontend shell

- [x] 4.1 Scaffold a Tauri + React + shadcn/ui frontend workspace
- [x] 4.2 Implement the session-list view and grouped per-session message-stream view
- [x] 4.3 Connect frontend state bootstrap to HTTP and live updates to the WebSocket stream

## 5. Cutover and documentation

- [ ] 5.1 Validate the new runtime against acceptance criteria while the old Tk entry remains available for development rollback
- [ ] 5.2 Switch the primary UI path to the Tauri frontend with the Python backend and retire Tk from the primary run path
- [ ] 5.3 Update README, config docs, and listener pitfalls documentation for the new architecture
