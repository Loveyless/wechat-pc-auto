## MODIFIED Requirements

### Requirement: Desktop shell settings SHALL cover all supported TTS providers
The system SHALL render provider-specific form branches for every TTS provider currently supported by the backend runtime on the mac-only branch: `macos_system`, `doubao`, `less_tts`, and `tencent_cloud`. The UI SHALL NOT allow selecting a provider that lacks a corresponding editable form branch, and SHALL treat the system-provider branch as a built-in macOS path without provider-private config fields.

#### Scenario: User selects the macOS system provider
- **WHEN** `tts.provider` is `macos_system`
- **THEN** the settings workspace renders the macOS-system guidance branch, hides unrelated cloud-provider secret inputs, and does not require a provider-private config path

#### Scenario: User selects the Doubao provider
- **WHEN** `tts.provider` is `doubao`
- **THEN** the settings workspace renders the Doubao-specific fields, including direct-input secret editors that echo the current value and visible non-secret provider settings

#### Scenario: User selects the Less TTS provider
- **WHEN** `tts.provider` is `less_tts`
- **THEN** the settings workspace renders the Less-TTS-specific fields, including a direct-input API key editor that echoes the current value and visible non-secret endpoint settings

#### Scenario: User selects the Tencent Cloud provider
- **WHEN** `tts.provider` is `tencent_cloud`
- **THEN** the settings workspace renders the Tencent-Cloud-specific fields, including direct-input secret editors that echo the current value and visible non-secret provider settings
