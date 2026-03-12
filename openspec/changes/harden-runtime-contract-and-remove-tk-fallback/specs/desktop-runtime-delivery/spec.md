## ADDED Requirements

### Requirement: The repository SHALL support only the Tauri desktop shell as the shipped desktop UI
The system SHALL define `backend_main.py + desktop-shell/` as the only supported desktop UI and delivery path. Legacy Tk UI code, packaging, and documentation SHALL be removed from the shipped product boundary.

#### Scenario: Developer checks supported desktop entrypoints
- **WHEN** a developer reads the repository documentation for supported desktop startup and delivery
- **THEN** the documented desktop UI path is the Tauri shell, with source-mode backend plus desktop-shell development flow retained only for development and diagnosis

#### Scenario: Legacy Tk packaging references are removed
- **WHEN** the repository ships the desktop delivery path after this change
- **THEN** legacy Tk packaging scripts, packaging docs, and supported-entrypoint references are no longer part of the shipped path

### Requirement: The repository SHALL provide fast regression validation separately from release packaging smoke
The system SHALL provide a lightweight regression workflow for the active desktop path that runs faster than release packaging smoke and does not build packaged artifacts.

#### Scenario: Pull request fast checks run
- **WHEN** the lightweight regression workflow executes for the active desktop path
- **THEN** it validates Python tests, desktop-shell frontend tests/build, and Rust tests without invoking packaged Windows build smoke

#### Scenario: Release packaging smoke runs
- **WHEN** the heavy release validation workflow executes
- **THEN** it remains focused on packaged desktop-shell verification and does not invoke legacy Tk packaging as part of the shipped desktop gate

### Requirement: Tk removal SHALL preserve shared runtime helpers still used by the supported path
The system SHALL remove Tk-only UI and packaging surfaces without deleting shared runtime, translation, TTS, and worker-support modules that are still used by `backend_main.py + desktop-shell/`.

#### Scenario: Tk-only code is removed
- **WHEN** the legacy Tk UI path is deleted
- **THEN** shared helper modules still required by the supported desktop runtime remain available and validated by non-Tk tests

#### Scenario: Mixed legacy tests are migrated before deletion
- **WHEN** the repository removes Tk-specific files
- **THEN** shared helper coverage is first separated from Tk-specific tests so Tk deletion does not erase coverage for surviving runtime code
