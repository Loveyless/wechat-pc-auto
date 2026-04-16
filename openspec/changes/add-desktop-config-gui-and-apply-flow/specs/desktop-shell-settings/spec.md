## ADDED Requirements

### Requirement: Desktop shell SHALL expose a settings workspace for persisted runtime configuration
The system SHALL provide a settings entry in the desktop shell that loads the runtime configuration DTO, presents editable fields for supported translate, display, and TTS settings, and surfaces save/apply feedback without replacing the existing runtime overview, session navigation, and message-reading shell structure.

#### Scenario: User opens settings from the desktop shell
- **WHEN** the user activates the settings entry
- **THEN** the shell loads the config DTO, renders the settings workspace, and keeps the rest of the shell connection model intact

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

### Requirement: Desktop shell SHALL separate persisted defaults from runtime-only toggles
The system SHALL keep the header runtime `tts-auto-read` toggle independent from the persisted `display.tts_auto_read_active_chat` setting shown in the settings workspace.

#### Scenario: User toggles runtime auto-read from the header
- **WHEN** the user changes the header auto-read toggle during a running session
- **THEN** the runtime action updates current runtime state without silently modifying the persisted settings form

#### Scenario: User edits the persisted startup default in settings
- **WHEN** the user changes `tts_auto_read_active_chat` in the settings workspace
- **THEN** the form becomes dirty for save, but the current runtime toggle state remains unchanged until a future backend restart
