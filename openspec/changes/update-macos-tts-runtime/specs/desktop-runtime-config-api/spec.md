## MODIFIED Requirements

### Requirement: Desktop runtime configuration API SHALL expose a complete safe editable DTO
The system SHALL provide a `GET /api/config` contract for the supported desktop runtime path that returns the editable translate, display, and TTS configuration needed by the desktop shell. The TTS payload SHALL expose only the providers supported by the mac-only branch in the editable enum, SHALL include a `macos_system` system-provider branch plus the existing cloud-provider branches, and SHALL keep the rest of the DTO/save structure unchanged. When the on-disk config still contains legacy `windows_system`, the API SHALL normalize that compatibility input into the supported macOS system-provider representation returned to the desktop shell.

#### Scenario: Desktop shell opens the settings screen on the supported branch
- **WHEN** the frontend requests `GET /api/config`
- **THEN** the response contains a complete editable DTO for translate, display, and TTS settings whose supported TTS provider enum is `macos_system`, `doubao`, `less_tts`, and `tencent_cloud`

#### Scenario: Desktop shell opens settings for a legacy runtime root
- **WHEN** the current config still stores `tts.provider=windows_system`
- **THEN** `GET /api/config` returns the supported macOS system-provider branch instead of exposing a Windows-only editable option

### Requirement: Desktop runtime configuration save SHALL validate and persist by file boundary
The system SHALL accept a configuration save request that validates edited fields using the same fail-fast rules as startup, keeps `listener.json` and provider-private TTS JSON as separate persistence boundaries, preserves unknown fields in both files, and writes all affected JSON files atomically with LF line endings. TTS saves SHALL persist `macos_system` as the built-in system-provider value for the supported branch, and cloud providers SHALL continue to persist their provider-private file paths through `tts.providers.<provider>.config_path`.

#### Scenario: User saves the macOS system provider
- **WHEN** the frontend sends a valid config save request with `tts.provider=macos_system`
- **THEN** the backend updates `listener.json` to keep the shared provider selection in `listener.json`, leaves cloud-provider private files untouched, and returns the updated snapshot for continued editing

#### Scenario: User saves after loading a legacy Windows system provider value
- **WHEN** the current runtime root started from `tts.provider=windows_system` and the user saves the normalized settings snapshot
- **THEN** the backend persists `tts.provider=macos_system` instead of rewriting the legacy Windows-only provider value
