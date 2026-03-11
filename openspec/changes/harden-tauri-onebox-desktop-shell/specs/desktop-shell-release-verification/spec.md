## ADDED Requirements

### Requirement: Sidecar packaging SHALL align with the real runtime dependency inventory
The system SHALL derive sidecar packaging from the actual backend and worker runtime dependency set, including explicit hidden imports where runtime loading is dynamic, and SHALL NOT encode speculative package assumptions as build requirements.

#### Scenario: Known dynamic runtime dependency is required by the packaged backend
- **WHEN** the backend runtime depends on a module that is loaded dynamically at runtime
- **THEN** the sidecar build configuration explicitly includes that dependency so the packaged executable can start successfully

#### Scenario: Proposed dependency is not part of the actual runtime path
- **WHEN** a package is not part of the backend or worker runtime path
- **THEN** the build hardening does not add or require that package without repository evidence

### Requirement: Desktop shell SHALL provide automated regression entry points for startup-critical logic
The system SHALL expose runnable automated checks for frontend connection-state handling, extracted Rust bootstrap logic, and other startup-critical logic that this change hardens.

#### Scenario: Frontend connection logic regresses
- **WHEN** the desktop-shell test command is executed
- **THEN** automated checks can detect regressions in managed-backend startup and connection-state behaviour

#### Scenario: Bootstrap logic is refactored into testable units
- **WHEN** pure or isolated Rust bootstrap logic is extracted from the shell entrypoint
- **THEN** automated Rust tests can validate the hardened behaviour without relying only on manual shell runs

### Requirement: Release-shell delivery SHALL include packaged smoke verification
The system SHALL verify the packaged shell by building the release artifact, launching it, checking backend health, and confirming bootstrap logs and second-launch reuse behaviour before treating the delivery path as accepted.

#### Scenario: Fresh release-shell smoke succeeds
- **WHEN** the release shell is built and launched in the smoke flow
- **THEN** `/healthz` becomes healthy and the bootstrap log records successful backend sidecar startup

#### Scenario: Release shell is launched again after the first run
- **WHEN** the already-running release shell is launched a second time during smoke validation
- **THEN** the verification confirms existing-window activation and backend reuse instead of extra sidecar spawning
