## ADDED Requirements

### Requirement: `/healthz` SHALL expose structured backend-runtime health for the desktop shell
The system SHALL return a JSON health payload for `/healthz` with a normative `status` field that distinguishes at least `starting`, `ok`, `startup_failed`, and `degraded`. The health contract SHALL describe backend-runtime availability for the shell and SHALL NOT be implemented as a fixed success stub.

#### Scenario: Backend startup is still in progress
- **WHEN** the backend process has started but runtime initialization has not finished yet
- **THEN** `/healthz` returns JSON with `status` set to `starting`

#### Scenario: Backend runtime is available to serve the shell
- **WHEN** the backend runtime and HTTP/WebSocket surfaces are initialized enough to serve the desktop shell
- **THEN** `/healthz` returns JSON with `status` set to `ok`

#### Scenario: Worker is waiting on WeChat but backend runtime is still healthy
- **WHEN** the backend runtime is available but the worker is currently waiting for WeChat or recovering external availability
- **THEN** `/healthz` still reports `status` as `ok` instead of treating the runtime as unready solely because `worker_state` is not `running`

#### Scenario: Startup fails before runtime becomes available
- **WHEN** backend startup throws or terminates before the runtime can serve the shell
- **THEN** `/healthz` returns JSON with `status` set to `startup_failed`

### Requirement: Shell bootstrap and release smoke SHALL treat only healthy runtime status as ready
The system SHALL treat the backend as bootstrap-ready only when `/healthz` returns the structured healthy status, and SHALL NOT infer readiness from an open TCP port, raw string matching, or a merely running process.

#### Scenario: Health endpoint reports non-ready status
- **WHEN** the shell bootstrap or release smoke probes `/healthz` and receives `starting`, `startup_failed`, `degraded`, malformed JSON, or a non-success HTTP response
- **THEN** the backend remains non-ready and the probe does not report a false ready transition

#### Scenario: Health endpoint reports healthy status
- **WHEN** the shell bootstrap or release smoke probes `/healthz` and receives a successful response with `status` equal to `ok`
- **THEN** the backend is treated as ready for shell startup verification
