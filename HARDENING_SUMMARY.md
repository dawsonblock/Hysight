# Hardening Summary

This pass tightened the repo's optional proof surfaces, runtime authority contract, and frontend fixture truth without changing the architecture.

## Optional proof surfaces

- Added `scripts/proof_mongo_live.py` and `scripts/proof_sidecar.py` as full local lifecycle harnesses for the opt-in live Mongo and memvid sidecar proofs.
- Added `scripts/proof_receipt.py` so the canonical proof entrypoints and the matching CI jobs emit machine-readable receipts under `artifacts/proof/`, with timestamped live-proof history under `artifacts/proof/history/`.
- Hardened aggregate receipts so they declare `covered_proof_steps` and `omitted_proof_steps`, and hardened frontend receipts so they declare the exact covered and passed stage names.
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

Recent verification on the supported bootstrap path:

- `./.venv/bin/python -m pytest backend/tests/test_server_bootstrap.py -q`
  - `42 passed, 1 deselected`
- `make proof-frontend`
  - runtime verification passed under Node `20.20.2` and Yarn `1.22.22`
  - fixture drift passed
  - lint passed
  - Jest: `5 passed test suites`, `19 passed tests`
  - build passed
  - receipt: `artifacts/proof/frontend.json`
- `./.venv/bin/python scripts/run_tests.py --baseline-step backend-baseline`
  - `98 passed, 1 deselected`
- `./.venv/bin/python scripts/check_repo_integrity.py`
  - passed

Current baseline contract enforced by `scripts/run_tests.py`:

- HCA pipeline proof: `7 passed`
- Backend baseline proof: `98 passed, 1 deselected`
- Contract conformance proof: `18 passed`
