## 1. Visual system foundation

- [ ] 1.1 Replace the current desktop-shell token set in `desktop-shell/src/index.css` with semantic workspace, surface, text, and state variables for the new light-theme layout
- [ ] 1.2 Expand `desktop-shell/src/components/ui/status-badge.tsx` and `desktop-shell/src/components/ui/button.tsx` so the shell can render distinct connection, fidelity, unread, and severity cues without repeated inline class logic
- [ ] 1.3 Add pure frontend view-model helpers and regression tests for connection-state summaries, badge tones, and empty-state branches used by the shell presentation

## 2. Runtime overview and layout split

- [ ] 2.1 Extract the top-level shell layout from `desktop-shell/src/components/shell/desktop-shell.tsx` into focused runtime-overview and shared state-panel components
- [ ] 2.2 Implement page-level treatments for `loading`, `starting`, `ready`, `startup_failed`, `degraded`, and `reconnecting` using the existing `useDesktopShell()` data without changing hook contracts

## 3. Session navigation and message reading

- [ ] 3.1 Extract a session-navigation component set that emphasizes selection, unread count, latest preview, update time, and preview-only fidelity
- [ ] 3.2 Extract a message-reading component set that prioritizes translated/display text, demotes raw preview metadata, and keeps `captureLevel` plus `pendingTranslation` visible as secondary cues
- [ ] 3.3 Add explicit no-session and no-message empty states so the shell stays readable when runtime data is sparse

## 4. Verification and documentation

- [ ] 4.1 Update any desktop-shell behaviour notes in `docs/wechat-listening-pitfalls.md` that would become inaccurate after the new state and fidelity presentation lands
- [ ] 4.2 Run the desktop-shell regression commands and manual walkthrough for overview, navigation, message-reading, and narrow-width rendering
