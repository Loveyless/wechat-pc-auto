## MODIFIED Requirements

### Requirement: The shipped desktop runtime SHALL own a single authoritative configuration schema
The system SHALL define one code-owned schema for the supported desktop runtime path that controls field defaults, validation, and loading rules for `backend_main.py + desktop-shell/`. That schema SHALL load provider-aware translate branches and per-provider TTS `config_path` maps while keeping backward-compatible reads for legacy `translate.deeplx_url(_env)`, legacy `translate.timeout_seconds`, and legacy `tts.config_path`. The shipped runtime SHALL NOT keep multiple independent schema definitions for the same fields.

#### Scenario: Main desktop runtime loads provider-aware listener configuration
- **WHEN** the supported desktop runtime loads `listener.json` with `translate.providers.<provider>` and `tts.providers.<provider>.config_path`
- **THEN** the defaults, validation rules, and active provider resolution come from the same authoritative schema owner used by the shipped path

#### Scenario: Main desktop runtime loads legacy translate and TTS path fields
- **WHEN** an existing runtime root still stores `translate.deeplx_url(_env)`, top-level `translate.timeout_seconds`, or single `tts.config_path`
- **THEN** startup loading still succeeds by treating those fields as read-only compatibility input instead of requiring a manual migration before boot

#### Scenario: Runtime docs describe supported configuration fields
- **WHEN** repository docs describe the supported desktop runtime configuration
- **THEN** the documented defaults and validation rules match the authoritative schema used by the shipped path
