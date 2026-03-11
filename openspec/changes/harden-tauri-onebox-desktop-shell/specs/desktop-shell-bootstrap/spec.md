## ADDED Requirements

### Requirement: Desktop shell SHALL determine managed-backend readiness from a stable health contract
The system SHALL treat the managed backend as ready only when the shell receives a successful `/healthz` response with the expected JSON health payload, and SHALL NOT rely on raw response-string matching.

#### Scenario: Backend health probe returns healthy JSON
- **WHEN** the managed shell probes `/healthz` and receives HTTP success with the expected health JSON payload
- **THEN** the shell marks the backend as ready and stops reporting it as still starting

#### Scenario: Backend health probe is not yet healthy
- **WHEN** the managed shell probes `/healthz` and receives a non-success response, malformed payload, or a payload that does not indicate healthy state
- **THEN** the shell keeps the backend in a non-ready state and does not report a false ready transition

### Requirement: Desktop shell SHALL expose explicit managed-backend startup states
The system SHALL represent managed backend startup as a distinct state from reconnect-after-disconnect behaviour so the frontend can distinguish startup in progress, startup failure, and ready connection.

#### Scenario: Cold start remains within backend bootstrap window
- **WHEN** the desktop shell launches and the managed backend has not become ready yet
- **THEN** the frontend reflects a startup-in-progress state instead of misreporting reconnect failure

#### Scenario: Managed backend fails before becoming ready
- **WHEN** the managed backend exits, times out, or reports a startup error before readiness is reached
- **THEN** the shell exposes startup failure rather than silently falling into generic reconnect semantics

### Requirement: Desktop shell SHALL behave as a single-instance application
The system SHALL allow only one active shell window per machine instance, and a second launch SHALL activate the existing window without disrupting the current backend reuse flow.

#### Scenario: User launches the shell a second time
- **WHEN** an existing shell window is already running and the user launches the shell again
- **THEN** the existing window is activated and no second shell window is created

#### Scenario: Existing backend is already running during second launch
- **WHEN** the user launches the shell again while the managed backend is already associated with the running shell
- **THEN** the second-launch handling preserves existing backend reuse behaviour and does not spawn an extra backend sidecar
