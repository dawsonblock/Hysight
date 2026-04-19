# Repair Summary

## Scope

This pass repaired and hardened the repository without changing its intended authority model:

- `hca/` remains the runtime core.
- `backend/` remains the FastAPI adapter.
- `frontend/` remains the operator UI.
- `memory_service/` remains the default local memory authority path.
- `memvid_service/` remains an optional sidecar path.

The goal was to make the default local proof surface honest and runnable from a clean environment, keep optional integrations out of baseline test collection, make subsystem authority explicit, reduce frontend/backend contract drift, and align the public docs with the implemented proof contract.

## Implemented Repairs

### Proof surface and dependency separation

- Added explicit backend proof tiers: `baseline`, `integration`, and `live`.
- Updated `backend/tests/conftest.py` to gate integration and live tests behind `--run-integration` and `--run-live`.
- Moved optional Mongo dependencies into `backend/requirements-integration.txt`.
- Removed `motor` and `pymongo` from the baseline runtime core requirements.
- Updated `backend/tests/test_status_live_mongo.py` so missing optional dependencies no longer break default collection.
- Refactored `scripts/run_tests.py` so the default command only runs the service-free local proof surface.
- Realigned `Makefile` targets and `.github/workflows/backend-proof.yml` to the new baseline/integration/live contract.
- Updated `backend/server_persistence.py` to point Mongo-enabled installs at `backend/requirements-integration.txt`.

### Subsystem authority and failure messaging

- Clarified `/api/subsystems` database and memory detail strings in `backend/server_subsystems.py` without changing the response schema.
- Updated `backend/server_memory_routes.py` so memory-route failures point operators to `/api/subsystems` without duplicating controller guidance.
- Updated `memory_service/controller.py` so Rust-sidecar failures explicitly identify the sidecar as the active memory authority and direct operators to `/api/subsystems`.
- Added a regression check in `backend/tests/test_server_bootstrap.py` to prevent duplicated `/api/subsystems` guidance from returning in route 503 responses.

### Frontend contract hardening

- Added a backend-owned generated fixture source in `frontend/src/lib/api.fixtures.generated.json`, with `frontend/src/lib/api.fixtures.js` as the thin wrapper consumed by tests and components.
- Expanded `frontend/src/lib/api.test.js` coverage for run summaries, events, artifacts, subsystem status, and memory APIs.
- Switched `frontend/src/components/OperatorConsole.test.js` to reuse the shared subsystem fixture.
- Switched `frontend/src/components/MemoryBrowser.test.js` to reuse the shared memory fixture.

### Documentation and verification workflow alignment

- Updated `README.md` to document the canonical baseline, frontend, integration, live Mongo, and live sidecar proof paths.
- Updated `docs/deployment.md` to match the canonical bootstrap and proof commands.
- Updated the proof documentation to note that receipts now declare covered and omitted proof steps, and that frontend receipts declare covered stage names.
- Updated `.github/agents/backend-verification.agent.md` so verification guidance matches the implemented proof contract.

## Verified Results

### Backend

Verified on the current proof contract and narrowed retests:

- `./.venv/bin/python -m pytest backend/tests/test_server_bootstrap.py -q`
  - `53 passed, 1 deselected`
- `./.venv/bin/python scripts/run_tests.py --baseline-step backend-baseline`
  - `98 passed, 1 deselected`
- `./.venv/bin/python scripts/check_repo_integrity.py`
  - passed
- `make proof-sidecar MEMORY_SERVICE_PORT=3032`
  - `13 passed, 2 skipped`
  - receipt: `artifacts/proof/live-sidecar.json`
- Latest live Mongo rerun on this branch
  - `make proof-mongo-live` passed against a disposable `mongo:7` container

### Frontend

Verified through the canonical frontend proof wrapper:

- `make proof-frontend`
  - runtime verification passed under Node `20.20.2` and Yarn `1.22.22`
  - fixture drift passed
  - lint passed
  - Jest: `5 passed test suites`, `19 passed tests`
  - build passed
  - receipt: `artifacts/proof/frontend.json`

## Remaining Limits

No unresolved documentation drift remains for this repair summary. The optional live Mongo and live sidecar paths remain explicit opt-in proof surfaces rather than part of the default service-free local proof path.

## Canonical Commands After Repair

- Baseline local proof surface: `python scripts/run_tests.py`
- Optional frontend proof: `make proof-frontend`
- Optional integration proof: `python scripts/run_tests.py --integration`
- Optional live Mongo proof harness: `make proof-mongo-live`
- Optional live Mongo narrow proof: `make test-mongo-live`
- Optional live sidecar proof wrapper: `make proof-sidecar`
- Optional live sidecar narrow proof: `make test-sidecar`
- Baseline bootstrap: `make test-bootstrap`
- Frontend bootstrap: `make test-bootstrap-frontend`
- Optional integration/live Mongo bootstrap: `make test-bootstrap-integration`
