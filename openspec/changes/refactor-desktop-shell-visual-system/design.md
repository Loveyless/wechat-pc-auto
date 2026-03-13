## Context

`desktop-shell/src/components/shell/desktop-shell.tsx` currently renders the page header, session list, runtime summary, and message cards in one file. The layout technically works, but it keeps most surfaces on the same card pattern and still relies on a small dark-theme token set from `desktop-shell/src/index.css`.  
The existing data layer already exposes the state needed for a better UI: connection states, session unread counts, preview-only markers, and message translation status are all present in `useDesktopShell()` and `desktop-shell/src/lib/shell-types.ts`. The missing part is presentation structure and reusable semantics, not backend data.  
Current regression coverage only locks connection-state transitions. There is no focused guardrail for how the shell derives and renders overview states, empty states, or message/session metadata priorities.

## Goals / Non-Goals

**Goals:**
- Split the shell into explicit runtime overview, session navigation, and message reading presentation units.
- Introduce semantic visual tokens for canvas, panel, text hierarchy, status severity, selection, and preview-only messaging in a single light theme.
- Preserve existing `HTTP + WebSocket` bootstrap/live-sync behaviour and existing connection-state semantics while making each state visually distinct.
- Keep message reading focused on translated/display text first, with preview-only and pending-translation signals remaining visible but secondary.
- Add regression coverage around the derived view-model logic that drives the new state and empty/error rendering.

**Non-Goals:**
- Changing any Python runtime, local API, WebSocket event, Tauri bootstrap, or health-check contract
- Adding settings screens, send-message controls, theme switching, or a second visual direction
- Introducing a large new component library or rewriting the shell state hook
- Re-defining TTS or translation runtime behaviour

## Decisions

### Decision: Split shell composition into page-level layout plus focused presentation components

The current one-file rendering makes hierarchy changes expensive and keeps the shell difficult to reason about. The shell will be decomposed into a top-level layout plus focused presentation components for runtime overview, session navigation, message stream, and shared empty-state/status blocks.

This keeps the backend hook unchanged while making each UI region independently testable and easier to evolve.

**Alternatives considered**
- **Only restyle the existing monolithic file**: rejected because it keeps structure, hierarchy, and regression boundaries tangled together.
- **Move state orchestration into new container hooks**: rejected because the current hook already owns the contract boundary and does not need a parallel state system.

### Decision: Replace bucket-style theme tokens with semantic workspace tokens

The current `background/card/primary/accent` palette is too generic to express runtime state, reading priority, and navigation emphasis. The shell will move to semantic tokens for canvas, surface layers, borders, text hierarchy, state severity, selection, and message metadata while keeping Tailwind v4 variables as the source of truth.

This lets presentational components share a consistent language instead of rebuilding ad-hoc class strings around generic colors.

**Alternatives considered**
- **Keep the existing token names and just swap hex values**: rejected because naming would still fail to communicate surface/state intent.
- **Introduce a separate design-token framework**: rejected because the repo already has a working Tailwind v4 path and does not need extra tooling for one frontend.

### Decision: Derive UI-specific labels and tones through pure view-model helpers

Connection summaries, state badge tones, session metadata labels, message fidelity markers, and empty-state copy will be derived from pure helpers near the shell components. These helpers can be tested without DOM-heavy tooling and keep rendering code from duplicating fragile conditional trees.

This is the narrowest way to gain regression coverage for the new UI logic without rewriting `useDesktopShell()` or adding a large testing dependency.

**Alternatives considered**
- **Inline all UI branching inside JSX**: rejected because it hides behaviour inside markup and makes regression coverage weak.
- **Add a full component-test stack first**: rejected because the main risk here is branching correctness, which pure helpers can cover with less churn.

### Decision: Preserve contract semantics and make degraded/empty states first-class in the shell layout

The new shell will continue to use the existing `ShellConnectionState`, session payloads, and message payloads. Instead of changing state values, the UI will promote them into a stable overview/status model that explicitly distinguishes `loading`, `starting`, `ready`, `startup_failed`, `degraded`, and `reconnecting`, along with no-session and no-message branches.

That keeps contract risk near zero while fixing the current under-specified frontend behaviour.

**Alternatives considered**
- **Change hook or backend payloads to add richer state fields**: rejected because current data is already sufficient and changing the contract would violate scope.
- **Treat all non-ready states as one generic warning**: rejected because the existing connection semantics are already important and tested.

## Risks / Trade-offs

- **[Light-theme readability regressions]** -> Use explicit contrast tokens for metadata, borders, warning states, and selected navigation items; verify with build plus manual narrow-width checks.
- **[Component splitting drifts into duplicated style logic]** -> Centralize status/session/message derivation in shared helpers and keep primitives (`StatusBadge`, `Button`) responsible for repeated visual patterns.
- **[Presentation-only change still affects documented operator expectations]** -> Update `docs/wechat-listening-pitfalls.md` if state or fidelity cues shown in the desktop shell become materially different.
- **[Missing UI regression coverage]** -> Add tests for the derived overview/status helpers so the most failure-prone rendering branches do not rely only on manual clicking.

## Migration Plan

1. Introduce semantic tokens and reusable presentation helpers without changing `useDesktopShell()` or backend contracts.
2. Extract runtime overview, session navigation, and message-reading components from the current monolithic shell.
3. Add regression tests for state/view-model derivation and keep the existing connection-state tests passing.
4. Run `npm test`, `npm run build`, and `cargo test`, then verify the shell manually against the documented states and narrow-width layout.

**Rollback strategy**
- Revert only the `desktop-shell/src/**` presentation changes and any related documentation updates.
- No config, runtime, API, or packaging migration is required for rollback.

## Open Questions

- None. The scope stays presentation-only unless implementation uncovers a real contract gap, in which case the change must be re-scoped instead of smuggling backend edits into this frontend change.
