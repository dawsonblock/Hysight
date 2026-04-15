# Hardening Summary

This pass tightened the repo's optional proof surfaces, runtime authority contract, and frontend fixture truth without changing the architecture.

## Optional proof surfaces

- Added `scripts/proof_mongo_live.py` and `scripts/proof_sidecar.py` as full local lifecycle harnesses for the opt-in live Mongo and memvid sidecar proofs.
- Added `scripts/proof_receipt.py` so both harnesses and the matching CI jobs emit machine-readable receipts under `test_reports/proof_receipts/`.
- Updated `Makefile` and `.github/workflows/backend-proof.yml` so `make proof-mongo-live` and `make proof-sidecar` are the full-harness entrypoints, while `make test-mongo-live` and `make test-sidecar` remain the narrow already-running-service paths.

## Package and runtime truth

- `scripts/run_tests.py` now fails fast if `hca` is not resolving from the editable `./hca` package source.
- `backend/server_bootstrap.py` and `tests/test_hca_pipeline.py` no longer inject `hca/src`; the supported path is editable installation through repo bootstrap.
- `scripts/run_backend.sh`, `README.md`, and `docs/deployment.md` now default to the repo-local `.venv` bootstrap flow and repeat the same package authority statement.

## Operator contract and fixtures

- Expanded `GET /api/subsystems` with explicit authority fields: `replay_authority`, `hca_runtime_authority`, `database.mongo_status_mode`, `database.mongo_scope`, `memory.memory_backend_mode`, and `memory.service_available`.
- Updated the strict schema in `contract/schema.json`, backend models in `backend/server_models.py`, backend payload assembly in `backend/server_subsystems.py`, frontend parsing in `frontend/src/lib/api.js`, and operator rendering in `frontend/src/components/OperatorConsole.js`.
- Added `scripts/export_api_fixtures.py` and committed `frontend/src/lib/api.fixtures.generated.json` as a backend-owned fixture source; `frontend/src/lib/api.fixtures.js` is now a thin wrapper over the generated JSON.

## Verification

- `python -m pytest backend/tests/test_server_bootstrap.py -q`
- `cd frontend && CI=1 npm test -- --runInBand --watch=false src/lib/api.test.js src/components/OperatorConsole.test.js src/components/MemoryBrowser.test.js`
- `python scripts/run_tests.py`

All of the above passed on this branch after the hardening changes.