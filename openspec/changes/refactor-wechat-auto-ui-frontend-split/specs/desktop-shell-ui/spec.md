## ADDED Requirements

### Requirement: Desktop shell renders session list and per-session message stream
The system SHALL provide a React/Tauri desktop shell that renders a session list and a per-session message stream as the primary UI experience.

#### Scenario: User opens the new desktop shell
- **WHEN** the Tauri desktop shell launches
- **THEN** it shows the session list and an active message-stream panel instead of the legacy Tk sidebar

### Requirement: Desktop shell initializes from backend snapshot and stays synced via WebSocket
The system SHALL use local HTTP endpoints for initial state bootstrap and SHALL use WebSocket events for ongoing live synchronization.

#### Scenario: Frontend reconnects to backend
- **WHEN** the desktop shell loads or reconnects
- **THEN** it rehydrates its initial state from HTTP and resumes live updates from WebSocket events

### Requirement: Desktop shell preserves translation display and TTS autoplay semantics
The system SHALL render translated message content in the new UI and SHALL preserve the existing TTS autoplay runtime behaviour for the active desktop flow.

#### Scenario: New translated message arrives for an active session
- **WHEN** a translated message event arrives for a visible session
- **THEN** the frontend renders the translated content and the backend preserves the configured TTS autoplay behaviour
