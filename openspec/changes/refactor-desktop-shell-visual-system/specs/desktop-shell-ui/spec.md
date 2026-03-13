## MODIFIED Requirements

### Requirement: Desktop shell renders session list and per-session message stream
The system SHALL provide a React/Tauri desktop shell that renders a runtime overview, a session navigation pane, and a per-session message-reading pane as the primary UI experience.

#### Scenario: User opens the desktop shell
- **WHEN** the Tauri desktop shell launches
- **THEN** it shows a runtime overview, a session navigation region, and an active message-reading region instead of a flat card wall

#### Scenario: User resizes the shell to a narrower window
- **WHEN** the desktop shell is rendered in a constrained width
- **THEN** the primary overview, navigation, and message-reading surfaces remain readable and operable without major content overlap

### Requirement: Desktop shell initializes from backend snapshot and stays synced via WebSocket
The system SHALL use local HTTP endpoints for initial state bootstrap, SHALL use WebSocket events for ongoing live synchronization, and SHALL render the existing connection-state values as distinct overview states without changing their underlying names.

#### Scenario: Frontend reconnects to backend
- **WHEN** the desktop shell loads or reconnects
- **THEN** it rehydrates its initial state from HTTP, resumes live updates from WebSocket events, and keeps the active UI state aligned with the current connection state

#### Scenario: Backend remains in a non-ready state
- **WHEN** the current connection state is `loading`, `starting`, `startup_failed`, `degraded`, or `reconnecting`
- **THEN** the shell shows a distinct overview/status treatment for that exact state rather than collapsing it into a generic warning

### Requirement: Desktop shell preserves translation display and TTS autoplay semantics
The system SHALL render translated or display message content as the primary reading layer in the shell and SHALL preserve the existing TTS autoplay runtime behaviour for the active desktop flow.

#### Scenario: New translated message arrives for an active session
- **WHEN** a translated message event arrives for a visible session
- **THEN** the frontend renders the translated or display content as the primary message text and the backend preserves the configured TTS autoplay behaviour

#### Scenario: Message is still preview-only or pending translation
- **WHEN** a message has `captureLevel=preview` or `pendingTranslation=true`
- **THEN** the shell keeps those cues visible as secondary fidelity/status indicators instead of presenting them as fatal errors

## ADDED Requirements

### Requirement: Desktop shell session navigation exposes scan-friendly hierarchy
The system SHALL render session navigation with stable emphasis for selection, unread count, latest preview, last update time, and preview-only fidelity so the user can scan and switch conversations quickly.

#### Scenario: User scans the session navigation pane
- **WHEN** multiple sessions with different unread counts, previews, and update times are present
- **THEN** the selected session, unread count, latest preview, and update metadata remain visually distinguishable without making every row the same weight

#### Scenario: Session only contains preview-derived messages
- **WHEN** a session reports `previewOnly=true`
- **THEN** the navigation row shows a non-error preview-only cue so the user can distinguish fidelity limits from transport failures

### Requirement: Desktop shell surfaces empty and abnormal states at page level
The system SHALL provide explicit page-level empty or abnormal-state treatments for no sessions, no messages, startup failure, degraded runtime, and reconnecting flow.

#### Scenario: No sessions are available
- **WHEN** the shell has no sessions after bootstrap
- **THEN** it shows an empty-state panel that explains the runtime has no conversation data instead of leaving the layout visually blank

#### Scenario: Active session has no messages
- **WHEN** the user selects a session whose message list is empty
- **THEN** the message-reading pane shows a no-message state that preserves the selected session context

#### Scenario: Backend startup fails
- **WHEN** the connection state is `startup_failed`
- **THEN** the shell shows a page-level failure treatment with the current error detail instead of only a low-visibility inline string
