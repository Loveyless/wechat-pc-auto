## Context

The repository has already switched its primary desktop path to `listener_app/backend_main.py + desktop-shell/`, with the old Tk entry kept only for development fallback and comparison.  
The current shell bootstrap in `desktop-shell/src-tauri/src/main.rs` still mixes backend reuse, readiness probing, sidecar spawning, bootstrap logging, and process cleanup in one file, while the frontend currently collapses cold-start delay into generic reconnect semantics.  
The delivery path is therefore exposed to three concrete risks at once: false backend-ready detection, ambiguous shell lifecycle behaviour on second launch, and insufficient automated verification around build-time packaging and release-shell startup.

## Goals / Non-Goals

**Goals:**
- Define a stable bootstrap contract between the Tauri shell and the Python backend.
- Make frontend startup semantics explicitly represent backend starting, backend ready, and startup failure.
- Enforce single-instance shell behaviour without breaking existing backend reuse safeguards.
- Align sidecar packaging with the real runtime dependency and hidden-import set.
- Add automated regression coverage and release-shell smoke verification for the desktop-shell path.
- Keep rollback bounded to the current `backend_main.py + desktop-shell/` main path and document the development-only fallback role of the Tk entry.

**Non-Goals:**
- Rewriting the Python backend runtime in Rust
- Replacing the existing backend mutex / marker reuse mechanism
- Reintroducing Tk as a formal shipped fallback UI
- Changing the `session-only + preview-only` monitoring contract
- Making the shell cross-platform

## Decisions

### Decision: Make backend readiness a structured bootstrap contract

The shell will treat backend readiness as a protocol check, not as a raw text guess.  
The ready probe must validate both HTTP success and the parsed JSON status from `/healthz`.

This keeps the bootstrap contract aligned with the actual local API and removes false negatives caused by formatting differences.

**Alternatives considered**
- **Keep string matching and only relax whitespace handling**: rejected because it still leaves readiness coupled to response formatting rather than a protocol contract.
- **Skip `/healthz` and infer readiness from socket connect alone**: rejected because an open port is not the same thing as a healthy runtime.

### Decision: Separate cold-start state from reconnect state

The frontend connection model will treat managed backend startup as a first-class phase distinct from reconnect-after-disconnect behaviour.  
The shell bootstrap layer remains responsible for managed-backend startup outcomes, while the frontend reflects those outcomes through explicit startup-state semantics.

This avoids showing `reconnecting` during normal cold start and makes startup failure diagnosable.

**Alternatives considered**
- **Keep the current `loading/reconnecting/degraded/ready` semantics and only tweak messages**: rejected because the state model itself is too coarse for managed startup.
- **Push all startup-state logic into the frontend only**: rejected because the shell bootstrap is the component that actually knows whether backend launch succeeded, is still starting, or has failed.

### Decision: Enforce single-instance at the shell layer and preserve backend reuse at the bootstrap layer

The shell will be single-instance: a second launch must activate the existing window instead of creating a new shell window.  
Existing backend mutex / marker logic remains responsible for backend reuse and sidecar deduplication.

This keeps window-lifecycle policy and backend-lifecycle policy separate instead of trying to overload one mechanism to do both.

**Alternatives considered**
- **Allow multiple shell windows against one backend**: rejected because the user already chose single-instance and multiple shells make active-window semantics ambiguous.
- **Use backend mutex alone as the only single-instance control**: rejected because backend reuse does not solve duplicate shell windows.

### Decision: Harden packaging against the real dependency inventory, not speculative packages

The packaging flow will inventory actual runtime imports and explicit hidden imports, then gate the build with packaged smoke checks.  
The change will not add `requests`-specific handling unless repository facts show `requests` is truly part of the runtime path.

This prevents the change from codifying a false root cause and keeps build hardening focused on real packaged behaviour.

**Alternatives considered**
- **Add `requests` and its transitive dependencies pre-emptively**: rejected because current repository evidence does not justify it.
- **Rely on PyInstaller auto-discovery only**: rejected because dynamic imports and packaging regressions are exactly the class of issue this hardening is supposed to catch.

### Decision: Layer verification into unit-level regression plus release-shell smoke

The delivery gate will include frontend connection tests, Rust bootstrap tests where pure logic is extracted, and a release-shell smoke path that verifies `/healthz`, bootstrap logs, and second-launch reuse behaviour.  
`npm run tauri build` alone is not sufficient evidence of a shippable shell.

**Alternatives considered**
- **Use manual shell clicking as the primary gate**: rejected because it is noisy, slow, and misses regressions in cold-start state handling.
- **Rely only on unit tests without release smoke**: rejected because packaged sidecar behaviour is one of the primary risks in this change.

## Risks / Trade-offs

- **[Shell bootstrap refactor touches a hot path]** → Keep the refactor module-oriented but incremental, and gate it with Rust/unit smoke coverage plus release-shell verification.
- **[Startup-state expansion can drift from frontend semantics]** → Define the startup states in the shell contract and keep frontend rendering mapped directly from that contract.
- **[Single-instance integration can interfere with existing backend reuse logs or focus behaviour]** → Keep window activation logic separate from backend marker logic and verify second-launch behaviour explicitly.
- **[Packaging hardening may surface previously hidden dependency drift]** → Fail fast in build-time and packaged smoke checks instead of allowing silent release regressions.

## Migration Plan

1. Fix the backend readiness contract first so later startup-state work is built on correct readiness signals.
2. Introduce explicit managed-backend startup-state handling in the shell/bootstrap layer and frontend connection layer.
3. Refactor bootstrap internals into smaller modules while keeping backend reuse semantics intact.
4. Enforce shell single-instance activation behaviour.
5. Align sidecar dependency inventory, build-time checks, and smoke verification.
6. Add or wire automated frontend, Rust, and release-shell regression coverage.
7. Update delivery and pitfalls docs to reflect the hardened shell path, the release gate, and the development-only fallback role of Tk.

**Rollback strategy**
- If any hardening step breaks `npm run tauri build`, release-shell cold start, `/healthz` readiness, or frontend startup semantics, stop distribution and revert to the last verified `backend_main.py + desktop-shell/` baseline.
- Keep `listener_app/sidebar_translate_listener.py` available only for development diagnosis and local comparison; do not re-promote it as the shipped primary UI.
- If only the managed Tauri shell path regresses while the local backend contract still works, use `backend_main.py + npm run dev` as an internal degradation path for diagnosis, not as release completion.

## Open Questions

- None. The plan now fixes single-instance as the desired shell policy, rejects speculative `requests` assumptions, and defines rollback boundaries for this hardening phase.
