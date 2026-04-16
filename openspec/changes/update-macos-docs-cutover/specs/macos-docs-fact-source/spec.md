## ADDED Requirements

### Requirement: Apple Silicon macOS branch docs SHALL expose one authoritative current-state fact source
The system SHALL document the current branch as an `Apple Silicon macOS` branch across `README.md`, `config/listener.md`, `docs/developer-guide.md`, and `docs/desktop-shell-build.md`, and SHALL NOT present Windows-only paths, artifact names, or commands as the default current-state workflow.

#### Scenario: Maintainer reads the documented startup and build entrypoints
- **WHEN** a maintainer follows the documented source-mode startup, Tauri dev, and release-app verification steps
- **THEN** the commands, runtime-root paths, and artifact names consistently describe `python3`, `~/Library/Application Support/com.wechatauto.shell`, `.app`, and mac target-triple sidecars instead of `.exe`, `%LOCALAPPDATA%`, `msi`, or `nsis`

#### Scenario: User reads the repository entry documentation
- **WHEN** a reader starts from `README.md`
- **THEN** the README identifies the branch as Apple Silicon macOS, routes maintainers to the deeper execution docs, and does not present old Windows launch steps as the current branch default

### Requirement: Migration-era Windows references SHALL be explicitly labeled as legacy reference material
The system SHALL keep any remaining Windows or pre-migration guidance only as explicitly labeled historical reference, and SHALL NOT leave those details mixed into the current default execution path without a legacy label.

#### Scenario: Maintainer reads the pitfalls document
- **WHEN** `docs/wechat-listening-pitfalls.md` preserves Windows/UIAutomation material for migration-era comparison
- **THEN** the document clearly labels that material as old implementation reference and keeps the current mac branch facts separated from it

#### Scenario: Developer scans for legacy keywords
- **WHEN** a maintainer scans the documentation for `.exe`, `%LOCALAPPDATA%`, `taskkill`, `uiautomation`, or `windows_system`
- **THEN** any remaining matches are either removed from current-state instructions or explicitly framed as legacy compatibility or migration reference

### Requirement: Documentation SHALL keep verified release and config guidance aligned with the current branch gate
The system SHALL keep configuration docs, developer docs, and build docs aligned with the current verified branch gate: source-mode startup, Tauri dev, `.app build + smoke` as the default release-app gate, and `DMG` build as GUI-only specialist verification.

#### Scenario: Maintainer follows the documented release verification gate
- **WHEN** a maintainer runs the release verification steps documented for the branch
- **THEN** the documented gate uses `npm run tauri -- build --bundles app` plus `scripts/smoke_desktop_shell_release.py --skip-build`, and documents `npm run tauri build` as separate `DMG` verification

#### Scenario: Maintainer reads config persistence guidance
- **WHEN** a maintainer reads `config/listener.md`
- **THEN** the document distinguishes repository `config/listener.json` from Tauri runtime-root config, describes the current `/api/config` save/apply boundary, and does not silently merge source-mode and packaged-shell config paths into one workflow
