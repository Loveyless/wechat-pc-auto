## Context

The repository has already committed to `listener_app/backend_main.py + desktop-shell/` as the shipped desktop path, while the legacy Tk entry remains in the tree only as historical fallback.  
Today the shell bootstrap, release smoke, and CI all rely on `/healthz`, but `listener_app/runtime_api.py` currently returns a fixed `{"status": "ok"}` payload that only proves the HTTP handler is alive. At the same time, `backend_main.py` starts `service.start()` before `api_server.start()`, so startup exceptions are invisible to `/healthz` because the HTTP layer never comes up in the failure case.  
The repository also still carries a second desktop UI path (`sidebar_translate_listener.py` + `sidebar_ui.py`), a second packaging route (`scripts/build_windows_exe.ps1`), and mixed tests (`tests/test_sidebar_listener_helpers.py`) that combine Tk-specific and shared runtime behavior in one file.

## Goals / Non-Goals

**Goals:**
- Make `/healthz` a real runtime-contract endpoint instead of a fixed success stub.
- Ensure shell bootstrap and release smoke treat readiness as “backend runtime is available to serve the shell,” not merely “a process opened a port.”
- Add a fast regression workflow that validates the active desktop path without requiring full Windows packaging smoke.
- Introduce a single code-owned configuration schema for the active desktop runtime path.
- Remove the Tk UI path, its packaging flow, and its docs/CI surface from the supported product boundary without deleting shared runtime/TTS helpers.

**Non-Goals:**
- Rewriting the backend runtime architecture from scratch
- Requiring `worker_state == running` before the shell may load
- Preserving the Tk UI as an official runtime fallback
- Reintroducing target-editing semantics into the main Tauri path
- Moving secrets into packaged artifacts

## Decisions

### Decision: `/healthz` will represent backend-runtime availability for the shell, not WeChat worker business success

The health contract will model the state of the local backend service that the Tauri shell depends on.  
It MUST distinguish at least:
- `starting`: process/API shell is booting or startup outcome is not finalized
- `ok`: backend runtime and HTTP API are initialized enough to serve `/api/runtime`, `/api/sessions`, `/api/config`, and WebSocket events to the shell
- `startup_failed`: startup failed before the runtime could become available
- `degraded`: backend process is alive but the runtime has entered a non-healthy post-start condition

`ok` SHALL NOT require `worker_state == running`. The backend must still be considered shell-ready when it is alive and supervising the worker, even if the worker is currently `waiting_wechat`, `window_lost`, or otherwise waiting on external WeChat availability.  
This is required because the shipped shell must be able to launch and expose runtime diagnostics even on machines where WeChat is not yet ready, and because CI release smoke currently runs without a real WeChat session.

**Alternatives considered**
- **Define health as `worker_state == running`**: rejected because it would make shell readiness depend on an external GUI app and break CI/diagnostic startup semantics.
- **Keep `/healthz` as a fixed `{"status":"ok"}` stub**: rejected because it produces false-green smoke and hides startup failures.

### Decision: Start or preserve the API layer early enough to expose startup failure

The backend entrypoint will be changed so startup failure is observable through the runtime contract instead of disappearing behind process exit.  
Implementation may either:
- start the API shell before driving backend runtime startup, or
- preserve a shared startup-state holder and keep the API layer alive while reporting `starting` or `startup_failed`

Regardless of the exact mechanics, the design outcome is fixed:
- the shell and smoke test can query `/healthz` during startup
- startup exceptions are translated into `startup_failed`
- the process does not pretend to be healthy if runtime initialization never completed

**Alternatives considered**
- **Keep `service.start()` before `api_server.start()` and only document the limitation**: rejected because it makes `startup_failed` impossible to expose and leaves the contract fake.
- **Expose startup failure only through logs**: rejected because bootstrap and CI need a machine-readable contract, not log scraping as the primary signal.

### Decision: Separate runtime health from detailed worker state

`/healthz` will expose the machine-readable service-health contract, while `/api/runtime` remains the detailed runtime/worker-state snapshot for the frontend.  
This avoids collapsing two different concerns:
- shell bootstrap readiness
- worker lifecycle/WeChat availability diagnostics

The frontend can continue to render `waiting_wechat`, `worker_backoff`, or other worker states from `/api/runtime`, while the shell bootstrap only depends on the coarse health contract.

**Alternatives considered**
- **Put all worker detail directly into `/healthz` and let the shell interpret everything**: rejected because it couples bootstrap to business-state detail and increases contract fragility.
- **Use only `/api/runtime` and remove `/healthz`**: rejected because bootstrap/release smoke need a small, stable readiness probe.

### Decision: Fast CI will stay on the active desktop path and omit packaging

The new fast regression workflow will validate the supported desktop path without building packaged artifacts.  
It will run:
- Python unit tests
- `desktop-shell` frontend tests
- `desktop-shell` frontend build
- Rust tests

The existing Windows packaging smoke remains the heavy release-oriented gate.

Using `windows-latest` for the fast workflow is acceptable if needed for test/environment compatibility, but the workflow MUST stay packaging-free so it remains materially faster and easier to diagnose than release smoke.

**Alternatives considered**
- **Keep only the packaging smoke workflow**: rejected because feedback is too slow and mixes logic regressions with packaging failures.
- **Replace packaging smoke entirely with fast CI**: rejected because packaged sidecar and release-shell behavior are still critical release risks.

### Decision: Configuration schema ownership will move to a main-path runtime module, with only a temporary Tk adapter if needed

The active desktop runtime path will own a single configuration loading/validation implementation, e.g. `listener_app/runtime_config.py`.  
Tk removal does not justify preserving Tk semantics in the main schema. If legacy Tk code temporarily needs compatibility before deletion, it must consume the main-path schema through a thin adapter, not continue to define schema behavior.

Special care is required for already-diverged fields like `listen.targets`:
- main path keeps only the semantics still relevant to the Tauri/runtime snapshot contract
- Tk-only target editing or target-driven filtering MUST NOT be reintroduced into the main runtime model

**Alternatives considered**
- **Keep duplicated config loading in both paths until Tk is deleted**: rejected because it guarantees further drift.
- **Force the main path to preserve all Tk semantics for “compatibility”**: rejected because it drags dead product behavior into the surviving path.

### Decision: Tk removal is a staged deletion, not a file purge

Tk removal will happen only after:
1. health contract hardening is done
2. fast CI exists
3. shared config/runtime tests are separated from Tk-specific tests

The deletion boundary is:
- remove Tk UI entrypoints, Tk UI implementation, Tk packaging script, Tk packaging docs, and Tk references in README/config docs/CI
- keep shared runtime, translate, TTS, worker-support, and config helpers that are still used by `backend_main.py + desktop-shell/`

`tests/test_sidebar_listener_helpers.py` must be split before deletion because it currently mixes shared helper coverage with Tk-specific UI behavior.

**Alternatives considered**
- **Delete all `sidebar_*` files in one sweep**: rejected because several of them are still used by the Tauri-backed runtime path.
- **Leave Tk code indefinitely but label it “legacy”**: rejected because it still imposes maintenance, docs, CI, and packaging cost.

## Risks / Trade-offs

- **[Health semantics become too broad or too strict]** → Keep `/healthz` narrowly about backend service availability for the shell, and keep worker diagnostics in `/api/runtime`.
- **[Changing startup order could introduce new bootstrap edge cases]** → Gate with Python API tests, Rust bootstrap tests, and release smoke before deleting any legacy path.
- **[Fast CI on Windows may still be slower than ideal]** → Accept Windows if needed for compatibility, but keep packaging and smoke out of the workflow so failures stay localized.
- **[Tk deletion can accidentally remove shared coverage]** → Split mixed tests first and only then remove Tk-specific files/tests.
- **[Config unification can silently preserve dead Tk semantics]** → Define the surviving main-path schema explicitly and force legacy compatibility through adapters only.

## Migration Plan

1. Introduce explicit runtime-health modeling and adjust `/healthz` plus its tests.
2. Update backend entrypoint/bootstrap mechanics so startup failure is observable through the health contract.
3. Update shell bootstrap and release smoke to consume the new health contract.
4. Add the fast regression workflow for the active desktop path.
5. Extract the main-path configuration schema/validation module and migrate the surviving runtime code to it.
6. Split shared-vs-Tk tests from `tests/test_sidebar_listener_helpers.py`.
7. Remove Tk UI code, Tk packaging script/docs, and Tk references from README/config docs/CI.
8. Re-run fast CI equivalents plus release smoke before treating Tk removal as complete.

**Rollback strategy**
- If runtime-health changes make shell bootstrap or release smoke unstable, revert to the last verified `backend_main.py + desktop-shell/` baseline before attempting Tk deletion.
- If config-schema extraction causes drift, keep the new main-path schema and reintroduce only a minimal temporary adapter for legacy code; do not restore duplicated schema definitions as the long-term fix.
- If Tk deletion reveals missing shared coverage, restore the affected shared tests/modules without re-promoting Tk as a supported UI.

## Open Questions

- None. The plan already commits to the Tauri path as the only supported desktop UI, treats Tk as removal scope rather than fallback scope, and defines the key health/config/test boundary decisions needed before implementation.
