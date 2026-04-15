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

- Added shared realistic backend fixtures in `frontend/src/lib/api.fixtures.js`.
- Expanded `frontend/src/lib/api.test.js` coverage for run summaries, events, artifacts, subsystem status, and memory APIs.
- Switched `frontend/src/components/OperatorConsole.test.js` to reuse the shared subsystem fixture.
- Switched `frontend/src/components/MemoryBrowser.test.js` to reuse the shared memory fixture.

### Documentation and verification workflow alignment

- Updated `README.md` to document the new baseline, integration, live Mongo, and live sidecar proof paths.
- Updated `docs/deployment.md` to match the canonical bootstrap and proof commands.
- Updated `.github/agents/backend-verification.agent.md` so verification guidance matches the implemented proof contract.

## Verified Results

### Backend

Verified by the backend verification agent and narrowed retests:

- `python scripts/run_tests.py`
  - HCA pipeline proof: 7 passed
  - Backend baseline proof: 70 passed
  - Contract conformance proof: 18 passed
- `python -m pytest backend/tests/test_server_bootstrap.py -q`
  - 32 passed after the memory-route guidance regression was added and retested
- `python -m pytest backend/tests/test_memvid_sidecar.py -q`
  - 15 skipped under the default opt-in policy
- `python -m pytest backend/tests/test_memvid_sidecar.py -q --run-integration`
  - 12 passed, 3 skipped
- `LIVE_MONGO_URL=mongodb://127.0.0.1:27017 LIVE_MONGO_DB_NAME=hysight_verify_live make test-mongo-live`
  - 1 passed against a disposable MongoDB 7 container
- Direct `POST /api/hca/memory/retrieve` failure probe
  - Confirmed the 503 detail now contains a single `/api/subsystems` reference with normal punctuation

### Frontend

Verified by the frontend verification agent with targeted Jest runs:

- `CI=true yarn --ignore-engines test --watch=false --runInBand --runTestsByPath src/lib/api.test.js`
  - 9 passed
- `CI=true yarn --ignore-engines test --watch=false --runInBand --runTestsByPath src/components/OperatorConsole.test.js src/components/MemoryBrowser.test.js`
  - 7 passed
- `docker run --rm -v "$PWD:/workspace" -w /workspace/frontend node:20.20.2 ...`
  - strict runtime-parity rerun under Node 20.20.2 and Yarn 1.22.22 passed with the same 9 + 7 test results

## Remaining Limits

No unresolved verification limits remain for this repair pass. The earlier live-Mongo and Node-20 caveats were closed with disposable Docker-based verification.

## Canonical Commands After Repair

- Baseline local proof surface: `python scripts/run_tests.py`
- Optional integration proof: `python scripts/run_tests.py --integration`
- Optional live Mongo proof: `make test-mongo-live`
- Optional live sidecar proof wrapper: `make proof-sidecar`
- Optional live sidecar narrow proof: `make test-sidecar`
- Baseline bootstrap: `make test-bootstrap`
- Optional integration/live Mongo bootstrap: `make test-bootstrap-integration`
