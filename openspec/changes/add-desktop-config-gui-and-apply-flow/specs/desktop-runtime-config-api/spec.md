## ADDED Requirements

### Requirement: Desktop runtime configuration API SHALL expose a complete safe editable DTO
The system SHALL provide a `GET /api/config` contract for the supported desktop runtime path that returns the editable translate, display, and TTS configuration needed by the desktop shell. Secret-like fields SHALL be returned only as metadata such as whether a value is configured, whether the current source is direct or environment-backed, and the configured environment variable name when applicable. Raw secret values SHALL NOT be returned.

#### Scenario: Desktop shell opens the settings screen
- **WHEN** the frontend requests `GET /api/config`
- **THEN** the response contains a complete editable DTO for supported translate, display, and TTS settings instead of the current partial snapshot

#### Scenario: Secret-backed configuration is already present
- **WHEN** the current config stores a secret directly or through `*_env`
- **THEN** `GET /api/config` reports only the secret metadata and never echoes the raw secret value

### Requirement: Desktop runtime configuration save SHALL validate and persist by file boundary
The system SHALL accept a configuration save request that validates edited fields using the same fail-fast rules as startup, keeps `listener.json` and provider-private TTS JSON as separate persistence boundaries, preserves unknown fields in both files, and writes all affected JSON files atomically with LF line endings.

#### Scenario: User submits a valid configuration change
- **WHEN** the frontend sends a valid config save request
- **THEN** the backend updates `listener.json` and any affected provider-private JSON files at their existing boundaries, preserves unknown fields, and returns a success payload

#### Scenario: User changes provider-specific TTS settings
- **WHEN** the save request targets `windows_system`, `doubao`, or `tencent_cloud`
- **THEN** provider selection remains in `listener.json` and provider-private fields remain in the provider config file instead of being merged into one payload

### Requirement: Desktop runtime configuration save SHALL fail without mutating files on invalid input
The system SHALL reject invalid configuration writes with field-level validation errors and SHALL keep the current on-disk configuration unchanged when validation fails.

#### Scenario: User submits an invalid value
- **WHEN** the save request contains an unsupported provider, missing required field, or invalid numeric range
- **THEN** the API responds with field-level validation errors and the existing config files remain unchanged

#### Scenario: User updates a secret field through write-only input
- **WHEN** the save request provides a new secret value or env indirection
- **THEN** the backend persists the new secret source without returning that raw value in the response
