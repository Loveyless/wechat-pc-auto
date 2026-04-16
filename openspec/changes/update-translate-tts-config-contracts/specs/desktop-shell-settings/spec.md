## MODIFIED Requirements

### Requirement: Desktop shell SHALL expose a settings workspace for persisted runtime configuration
The system SHALL provide a settings entry in the desktop shell that loads the runtime configuration DTO, presents editable fields for supported translate, display, and TTS settings, and surfaces save/apply feedback without replacing the existing runtime overview, session navigation, and message-reading shell structure. The translate section SHALL render provider-aware branches for `deeplx`, `openai_compatible`, and `passthrough`.

#### Scenario: User opens settings from the desktop shell
- **WHEN** the user activates the settings entry
- **THEN** the shell loads the config DTO, renders the settings workspace, and keeps the rest of the shell connection model intact

#### Scenario: User selects the DeepLX provider
- **WHEN** `translate.provider` is `deeplx`
- **THEN** the settings workspace renders the DeepLX URL direct-input editor and provider timeout field, prefilled with the current editable value

#### Scenario: User selects the OpenAI-compatible provider
- **WHEN** `translate.provider` is `openai_compatible`
- **THEN** the settings workspace renders `base_url`, `model`, `api_key`, and timeout controls for that provider and treats `api_key` as a direct-input field that echoes the current editable value

#### Scenario: Save succeeds on a save-only connection
- **WHEN** the frontend saves a valid configuration while apply is unavailable
- **THEN** the shell shows that the config is saved and that backend restart is still required before the new settings take effect

### Requirement: Desktop shell settings SHALL cover all supported TTS providers
The system SHALL render provider-specific form branches for every TTS provider currently supported by the backend runtime: `windows_system`, `doubao`, `less_tts`, and `tencent_cloud`. The UI SHALL NOT allow selecting a provider that lacks a corresponding editable form branch.

#### Scenario: User selects the Windows system provider
- **WHEN** `tts.provider` is `windows_system`
- **THEN** the settings workspace renders the Windows-system-specific fields and hides unrelated cloud-provider secret inputs

#### Scenario: User selects the Doubao provider
- **WHEN** `tts.provider` is `doubao`
- **THEN** the settings workspace renders the Doubao-specific fields, including direct-input secret editors that echo the current value and visible non-secret provider settings

#### Scenario: User selects the Less TTS provider
- **WHEN** `tts.provider` is `less_tts`
- **THEN** the settings workspace renders the Less-TTS-specific fields, including a direct-input API key editor that echoes the current value and visible non-secret endpoint settings

#### Scenario: User selects the Tencent Cloud provider
- **WHEN** `tts.provider` is `tencent_cloud`
- **THEN** the settings workspace renders the Tencent-Cloud-specific fields, including direct-input secret editors that echo the current value and visible non-secret provider settings

## ADDED Requirements

### Requirement: Desktop shell settings SHALL prioritize core provider setup over secondary TTS tuning
The system SHALL keep core translate/TTS setup fields visible on the first screen and move secondary TTS tuning behind provider-specific advanced sections instead of presenting all TTS numeric knobs as equal first-screen controls.

#### Scenario: User opens a cloud TTS provider form
- **WHEN** the settings workspace renders `doubao` or `tencent_cloud`
- **THEN** endpoint, credentials, and provider path remain directly visible while secondary tuning fields are grouped in an advanced section
