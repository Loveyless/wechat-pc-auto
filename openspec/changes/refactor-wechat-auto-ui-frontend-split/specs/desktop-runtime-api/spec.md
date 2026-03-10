## ADDED Requirements

### Requirement: Backend exposes desktop runtime snapshot APIs
The system SHALL expose local HTTP endpoints that let the desktop frontend read the current runtime state, discover sessions, read configuration, and trigger explicit runtime control actions without depending on Tk internals.

#### Scenario: Frontend bootstraps from local backend
- **WHEN** the desktop frontend starts
- **THEN** it can fetch runtime state and session data from local HTTP endpoints before opening the live event stream

### Requirement: Backend streams live desktop events over WebSocket
The system SHALL expose a local WebSocket stream for live session, message, translation, TTS, backend-state, and error events using stable event names and payload shapes.

#### Scenario: New desktop event reaches frontend
- **WHEN** the backend receives a new session or message update
- **THEN** it publishes a WebSocket event that the frontend can consume without parsing worker stdout directly

### Requirement: Backend remains independent from the Tk rendering path
The system SHALL keep runtime supervision, session/message state, translation flow, and TTS state available without requiring Tk UI objects or Tk-only render callbacks.

#### Scenario: Backend runs without Tk renderer
- **WHEN** the local backend is started for the new desktop shell
- **THEN** it can supervise the worker and maintain runtime state without constructing the legacy Tk UI
