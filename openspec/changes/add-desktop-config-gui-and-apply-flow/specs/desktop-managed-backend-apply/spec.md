## ADDED Requirements

### Requirement: Managed apply SHALL restart only a shell-owned backend sidecar
The system SHALL allow “save and apply” only when the desktop shell is connected to the backend sidecar instance that it currently owns. The apply path SHALL restart that owned backend after a successful save, wait for health recovery, and reconnect the shell without closing the main window.

#### Scenario: User saves and applies while connected to an owned managed backend
- **WHEN** the config save succeeds and the shell owns the current backend sidecar
- **THEN** the shell restarts only that owned backend, waits for it to become healthy again, and reconnects to the refreshed runtime

#### Scenario: Shell is connected to a reused or external backend
- **WHEN** the current backend is not owned by the shell instance
- **THEN** the apply action is unavailable and the shell offers save-only guidance instead of attempting a restart

### Requirement: Managed apply SHALL never run after a failed save
The system SHALL execute managed apply only after configuration persistence succeeds. A failed save SHALL block any restart attempt and SHALL leave the current runtime process untouched.

#### Scenario: Save validation fails before apply
- **WHEN** the user requests save and apply but the config payload is invalid
- **THEN** the backend returns validation errors, the shell does not invoke managed restart, and the current runtime keeps running with the previous configuration
