## Why

The desktop shell already owns the primary UI path, but its current presentation still looks like a developer scaffold: runtime status, session navigation, and message reading all compete for the same visual weight.  
This change is needed now because the backend/runtime split is already in place, so the next correctness gain is making the frontend express state, priority, and message fidelity without changing the local HTTP or WebSocket contracts.

## What Changes

- Restructure the desktop shell presentation into three explicit layers: runtime overview, session navigation, and message reading.
- Replace the current generic dark token bucket with a semantic visual system tuned for a single light workspace theme.
- Expand frontend presentation primitives so connection states, preview-only fidelity, pending translation, unread counts, and empty/error states are visually distinct.
- Extract the current monolithic shell rendering into focused presentational components that continue to consume the existing `useDesktopShell()` state.
- Add frontend regression coverage for the derived state/view-model branches that drive the new status and empty-state rendering.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `desktop-shell-ui`: refine the desktop shell hierarchy, state visibility, session navigation readability, and message reading emphasis while preserving the existing HTTP bootstrap, WebSocket sync, translation display, and TTS autoplay semantics.

## Impact

- **Affected code**:
  - `desktop-shell/src/components/shell/**`
  - `desktop-shell/src/components/ui/status-badge.tsx`
  - `desktop-shell/src/components/ui/button.tsx`
  - `desktop-shell/src/index.css`
  - `desktop-shell/src/hooks/**` or adjacent pure view-model helpers/tests needed for rendering-state regression coverage
  - `docs/wechat-listening-pitfalls.md`
- **Affected APIs / contracts**:
  - No backend API or Tauri bootstrap contract changes are intended
  - Existing `ShellConnectionState`, session/message payloads, and local `HTTP + WebSocket` usage remain unchanged
- **Dependencies / systems**:
  - React frontend composition
  - Tailwind v4 theme variables and utility usage
  - `class-variance-authority`-based UI primitives
