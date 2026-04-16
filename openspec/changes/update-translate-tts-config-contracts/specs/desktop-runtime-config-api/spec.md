## MODIFIED Requirements

### Requirement: Desktop runtime configuration API SHALL expose a complete safe editable DTO
The system SHALL provide a `GET /api/config` contract for the supported desktop runtime path that returns the editable translate, display, and TTS configuration needed by the desktop shell. The translate payload SHALL separate shared fields from `translate.providers.<provider>` branches, including `deeplx`, `openai_compatible`, and `passthrough`. Secret-like fields SHALL return the current editable value so the settings UI can prefill direct-input forms. When a value is still coming from legacy `*_env` config, the DTO SHALL continue to expose `source=env` and the configured environment variable name as compatibility metadata.

#### Scenario: Desktop shell opens the settings screen
- **WHEN** the frontend requests `GET /api/config`
- **THEN** the response contains a complete editable DTO for supported translate, display, and TTS settings instead of the current partial snapshot

#### Scenario: Translate provider branches include required provider fields
- **WHEN** the frontend loads a config DTO for translate settings
- **THEN** shared translate fields are separate from `translate.providers.deeplx`, `translate.providers.openai_compatible`, and `translate.providers.passthrough`, and each non-secret provider field needed by the selected branch is present

#### Scenario: Secret-backed configuration is already present
- **WHEN** the current config stores a secret directly or through `*_env`
- **THEN** `GET /api/config` returns the current effective value for editing and, when applicable, marks that the source is still legacy env-backed

### Requirement: Desktop runtime configuration save SHALL validate and persist by file boundary
The system SHALL accept a configuration save request that validates edited fields using the same fail-fast rules as startup, keeps `listener.json` and provider-private TTS JSON as separate persistence boundaries, preserves unknown fields in both files, and writes all affected JSON files atomically with LF line endings. Translate saves SHALL accept `secret_updates.translate.<provider>` direct-value payloads, and TTS saves SHALL persist provider-private file paths through `tts.providers.<provider>.config_path` instead of a single drifting `tts.config_path`.

#### Scenario: User submits a valid provider-aware translate change
- **WHEN** the frontend sends a valid config save request with `translate.providers.<provider>` and matching `secret_updates.translate.<provider>`
- **THEN** the backend updates `listener.json` to the new provider-aware shape, preserves unknown fields, clears any legacy `*_env` field for the same secret, and returns an updated snapshot for continued editing

#### Scenario: User changes provider-specific TTS settings
- **WHEN** the save request targets `windows_system`, `doubao`, or `tencent_cloud`
- **THEN** provider selection remains in `listener.json`, provider-private fields remain in the provider config file, and inactive provider `config_path` entries are preserved instead of being dropped

### Requirement: Desktop runtime configuration save SHALL fail without mutating files on invalid input
The system SHALL reject invalid configuration writes with field-level validation errors and SHALL keep the current on-disk configuration unchanged when validation fails.

#### Scenario: User submits an invalid translate provider payload
- **WHEN** the save request selects an active translate provider whose required fields are missing or invalid
- **THEN** the API responds with field-level validation errors and the existing config files remain unchanged

#### Scenario: User updates a translate secret through direct input
- **WHEN** the save request provides `{ "value": "..." }` for DeepLX or `openai_compatible.api_key`
- **THEN** the backend persists that direct value, clears any legacy `*_env` field for the same secret, and returns the updated snapshot for continued editing
