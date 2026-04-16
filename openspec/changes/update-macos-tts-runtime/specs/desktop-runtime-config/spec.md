## MODIFIED Requirements

### Requirement: The shipped desktop runtime SHALL own a single authoritative configuration schema
The system SHALL define one code-owned schema for the supported desktop runtime path that controls field defaults, validation, and loading rules for `backend_main.py + desktop-shell/`. That schema SHALL treat `macos_system` as the shipped built-in system TTS provider for the supported branch, SHALL continue to load cloud-provider `tts.providers.<provider>.config_path` branches through the same authoritative owner, and SHALL accept legacy `windows_system` values only as compatibility input that resolves to the macOS system-speech path instead of Windows-only playback code. The shipped runtime SHALL NOT keep multiple independent schema definitions for the same fields.

#### Scenario: Main desktop runtime loads supported macOS TTS configuration
- **WHEN** the supported desktop runtime loads `listener.json` with `tts.provider=macos_system` or one of the supported cloud providers
- **THEN** the defaults, validation rules, and active provider resolution come from the same authoritative schema owner used by the shipped path

#### Scenario: Main desktop runtime loads a legacy Windows system provider value
- **WHEN** an existing runtime root still stores `tts.provider=windows_system`
- **THEN** startup loading succeeds by treating that value as legacy compatibility input, routes the runtime onto the macOS system-speech path, and avoids calling Windows-only playback infrastructure

#### Scenario: Runtime docs describe supported TTS configuration fields
- **WHEN** repository docs describe the supported desktop runtime configuration
- **THEN** the documented provider enum, default value, and compatibility notes match the authoritative schema used by the shipped path
