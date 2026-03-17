## ADDED Requirements

### Requirement: The shipped desktop runtime SHALL own a single authoritative configuration schema
The system SHALL define one code-owned schema for the supported desktop runtime path that controls field defaults, validation, and loading rules for `backend_main.py + desktop-shell/`. The shipped runtime SHALL NOT keep multiple independent schema definitions for the same fields.

#### Scenario: Main desktop runtime loads listener configuration
- **WHEN** the supported desktop runtime loads `listener.json` and related provider config
- **THEN** the defaults and validation rules come from one authoritative schema owner instead of duplicated loaders in multiple runtime entrypoints

#### Scenario: Runtime docs describe supported configuration fields
- **WHEN** repository docs describe the supported desktop runtime configuration
- **THEN** the documented defaults and validation rules match the authoritative schema used by the shipped path

### Requirement: Main-path schema SHALL preserve only semantics still used by the Tauri desktop path
The system SHALL treat diverged legacy fields according to the active Tauri runtime contract, and SHALL NOT preserve Tk-only behavior in the surviving main schema.

#### Scenario: `listen.targets` is present in configuration
- **WHEN** the shipped desktop runtime loads a configuration that still includes `listen.targets`
- **THEN** the main path does not reintroduce target-driven monitoring scope and continues to use the Tauri/runtime contract semantics for the supported path

#### Scenario: Legacy compatibility is still temporarily required before Tk removal
- **WHEN** old Tk code still needs to read configuration during migration
- **THEN** it consumes the authoritative main-path schema through a temporary adapter instead of defining independent schema behavior
