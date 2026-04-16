# Hysight Repair Report

Historical note: this report captures the repair pass at the time it landed. For the current canonical proof contract, baseline counts, and receipt locations, use `README.md`, `BOOTSTRAP.md`, and `docs/deployment.md`.

## Current architecture summary

Hysight now presents one clear backend authority path:

- HTTP entrypoint: `backend.server:app`
- Backend execution adapter: `hca/src/hca/api/runtime_actions.py`
- Runtime authority: `hca/src/hca/runtime/runtime.py`
- Replay-backed read surface: `hca/src/hca/api/run_views.py`
- Frontend client authority: `frontend/src/lib/api.js`

The backend adapter layer has been decomposed so `backend/server.py` now owns startup, configuration, database lifecycle, dependency wiring, and router composition only. Status routes, HCA routes, memory routes, backend-only models, bootstrap, and SSE streaming now live in dedicated backend modules.

The default runtime remains Python-backed memory with no required Mongo instance and no required Rust sidecar. Mongo-backed `/api/status` persistence and the Rust memvid sidecar remain supported optional modes.

## What was inconsistent before

- The top-level runtime smoke tests allowed `failed` as an acceptable outcome for a passing run.
- The backend approval completion test could skip instead of failing when the run never reached `awaiting_approval`.
- The backend control surface was overloaded in `backend/server.py`, mixing startup/config, DB wiring, status routes, HCA routes, approval routes, memory routes, and SSE streaming.
- The frontend had real Jest and build tooling, but no CI proof and no runnable lint command.
- Documentation mixed local opt-in behavior with CI behavior for the live sidecar proof and did not clearly call out the frontend proof surface.
- The shared frontend API-authority guard did not account for a dedicated API client test file.

## What changed

### Proof tightening

- Tightened the canonical smoke path so non-mutation runtime smoke now must complete successfully instead of accepting `failed`.
- Tightened approval-path proof so a mutation request must actually enter `awaiting_approval`; approve and deny paths now prove completed and halted terminal states directly.
- Added focused invariants for:
  - SSE success signaling
  - SSE error signaling
  - explicit but non-fatal planner memory retrieval failure behavior

### Backend consolidation

- Extracted backend bootstrap and path/env loading into `backend/server_bootstrap.py`.
- Extracted backend-only response models into `backend/server_models.py`.
- Extracted `/api/` and `/api/status` registration into `backend/server_status_routes.py`.
- Extracted `/api/hca/*` run, replay, approval, and drilldown registration into `backend/server_hca_routes.py`.
- Extracted `/api/hca/memory/*` registration into `backend/server_memory_routes.py`.
- Extracted SSE logic into `backend/server_streaming.py`.
- Reduced `backend/server.py` to configuration, DB lifecycle, router composition, and app factory responsibilities.

### Frontend proof wiring

- Added a real ESLint 9 flat config at `frontend/eslint.config.js`.
- Added a `yarn lint` script to `frontend/package.json`.
- Added `frontend/src/lib/api.test.js` to prove API-base normalization, canonical run list query construction, canonical approval route construction, and response-shape rejection on boundary drift.
- Added `.github/workflows/frontend-proof.yml` to run install, lint, Jest, and build in CI.
- Cleaned up the small number of real lint failures exposed by that proof surface.

### Documentation repair

- Updated `README.md` so frontend proof, optional Mongo behavior, optional sidecar mode, and current CI semantics match the code and workflows.
- Updated `compose.sidecar.yml` header comments so the Rust sidecar overlay is clearly documented as opt-in over the default `compose.yml` path.

## Modified files

- `README.md`
- `backend/server.py`
- `backend/tests/test_server_bootstrap.py`
- `compose.sidecar.yml`
- `frontend/package.json`
- `frontend/src/components/HCAChat.js`
- `frontend/src/components/HCAChat.test.js`
- `frontend/src/components/ui/badge.jsx`
- `frontend/src/components/ui/calendar.jsx`
- `frontend/src/hooks/use-toast.js`
- `.github/workflows/frontend-proof.yml`
- `backend/server_bootstrap.py`
- `backend/server_hca_routes.py`
- `backend/server_memory_routes.py`
- `backend/server_models.py`
- `backend/server_status_routes.py`
- `backend/server_streaming.py`
- `frontend/eslint.config.js`
- `frontend/src/lib/api.test.js`

## Behaviors now enforced by tests

- `tests/test_hca_pipeline.py` now requires the default smoke run to complete and the memory-write smoke path to stop in `awaiting_approval` instead of tolerating failure.
- `backend/tests/test_hca.py` now proves:
  - healthy completed runs include success receipts and no `run_failed` key events
  - approval-gated runs actually pause before execution
  - approval grants resume to `completed`
  - approval denials halt without execution
  - SSE emits `done` on success
  - SSE emits `error` on runtime failure
  - planner memory retrieval failure is explicit in summary state but does not crash the run
- `backend/tests/test_server_bootstrap.py` still enforces the single frontend API authority and now explicitly allows the dedicated client-boundary test file as part of that authority surface.
- `backend/tests/test_contract_conformance.py` still pins the HTTP contract while the backend refactor keeps route behavior stable.
- `frontend/src/lib/api.test.js` now proves canonical frontend client behavior against the real API helper surface.
- Existing frontend Jest suites still prove the live operator shell, replay console, and memory drawer behaviors.

## Optional subsystems

- Rust memvid sidecar: still optional locally, still supported, now documented honestly as an overlay mode. Local live-sidecar proof remains opt-in. CI also exercises the supported sidecar mode.
- Mongo-backed `/api/status` persistence: still optional. If `MONGO_URL` and `DB_NAME` are both absent, HCA and memory routes remain available and `/api/status` intentionally returns `503`. Partial configuration still fails fast.

## Limitations still remaining

- I did not run the live Rust sidecar proof locally in this pass, so local evidence still does not include a fresh sidecar health/ingest/retrieve/restart run.
- I did not run a live Mongo-backed `/api/status` integration test against a real Mongo instance in this pass.
- The frontend is still a JavaScript project with `jsconfig.json`, not a true statically typed frontend. The new proof surface is lint + Jest + build + API boundary tests, not full type-checking.
- `backend/server.py` is much smaller and the route/stream logic is split, but database configuration and lifecycle still live in the main backend adapter rather than a fully separate persistence module.

## Exact commands run

### Focused verification

```bash
python -m pytest tests/test_hca_pipeline.py backend/tests/test_hca.py -q
python -m pytest backend/tests/test_server_bootstrap.py backend/tests/test_hca.py backend/tests/test_contract_conformance.py tests/test_hca_pipeline.py -q
cd frontend && yarn lint
cd frontend && CI=true yarn test --watch=false --runInBand
cd frontend && yarn build
```

### Canonical proof path

```bash
python scripts/run_tests.py
cd frontend && yarn lint && CI=true yarn test --watch=false --runInBand && yarn build
```

## Exact test and build results

### Canonical backend proof

`python scripts/run_tests.py`

- HCA pipeline proof: `7 passed`
- Backend local proof: `62 passed`
- Contract conformance proof: `14 passed`
- Backend full proof: `88 passed, 3 skipped`
- Overall result: `All 4 proof step(s) passed.`

### Focused backend slice

`python -m pytest backend/tests/test_server_bootstrap.py backend/tests/test_hca.py backend/tests/test_contract_conformance.py tests/test_hca_pipeline.py -q`

- Result: `75 passed`

### Frontend proof

`cd frontend && yarn lint`

- Result: passed

`cd frontend && CI=true yarn test --watch=false --runInBand`

- Result: `5 passed test suites`, `12 passed tests`

`cd frontend && yarn build`

- Result: build succeeded
- Output sizes after gzip:
  - JavaScript: `171.48 kB`
  - CSS: `9.2 kB`

## Blunt assessment

This repository is not just cleaner than before. The default backend proof path is materially more trustworthy now because it no longer accepts failed runtime states as success, approval behavior is asserted instead of skipped, the SSE path has direct proof, the frontend is finally under real CI proof, and the backend adapter layer is less likely to keep accreting unrelated concerns in one file.

It is still not fully proven across every supported mode. The local pass did not include a fresh live Rust sidecar run or a real Mongo-backed status integration run, and the frontend still lacks a true static type-checker. So the honest conclusion is: the default bounded runtime and operator surface are now robustly provable locally, but the optional sidecar and Mongo modes remain supported rather than exhaustively re-proven in this session.
