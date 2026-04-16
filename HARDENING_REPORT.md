# Hardening Report

Historical note: this report captures the hardening pass at the time it landed. For the current canonical bootstrap path, proof commands, and receipt locations, use `README.md`, `BOOTSTRAP.md`, and `docs/deployment.md`.

This document records the production-hardening work completed in the current implementation pass.

## Scope Completed

- Runtime persistence now writes `run.json` atomically and serializes per-run read/modify/write operations with a re-entrant run lock.
- Approval authority now fails closed against replay-backed approval state instead of trusting stale in-memory context alone.
- Eval-only auto-grant tokens are randomized instead of deterministic.
- The backend now exposes `GET /api/subsystems` as the operator-facing source of truth for database, memory, storage, and LLM readiness.
- The replay console now renders subsystem health and replay-backed approval reason, binding, and policy context.
- The live chat approval card now renders the same replay-backed approval context instead of only showing approval status and action arguments.
- The public run-summary contract now pins the structured `approval` payload instead of treating it as a loose object.
- The backend proof surface now includes a halted-run SSE `done` case so non-success terminal summaries are proven to stay replay-backed.

## Behavior Notes

- `POST /api/status` and `GET /api/status` remain optional and continue returning `503` when Mongo-backed persistence is disabled.
- `GET /api/subsystems` is the always-available degraded-mode surface for operator health visibility.
- Approval transitions remain pending-only at the decision routes, while runtime resume accepts approvals in `pending` or `granted` state.
- Denied approvals still halt the run on resume.
- Reused approvals now fail explicitly as consumed rather than silently degrading into a generic missing-pending-approval error.

## Proof Executed

- Backend/runtime targeted proof:

```bash
python -m pytest backend/tests/test_server_bootstrap.py backend/tests/test_contract_conformance.py backend/tests/test_hca.py hca/tests/unit/test_approval_edge_cases.py -q
```

Result: `78 passed in 4.64s`

- Frontend targeted proof:

```bash
cd frontend && CI=true yarn test --watch=false --runInBand --runTestsByPath src/lib/api.test.js src/components/OperatorConsole.test.js src/components/HCAChat.test.js
```

Result: `12 passed`

- Frontend static analysis:

```bash
cd frontend && yarn eslint src/lib/api.js src/lib/api.test.js src/components/OperatorConsole.js src/components/OperatorConsole.test.js src/components/HCAChat.js src/components/HCAChat.test.js
```

Result: passed

- Default backend proof surface:

```bash
python scripts/run_tests.py
```

Result: `HCA pipeline proof 7 passed`, `Backend local proof 68 passed`, `Contract conformance proof 18 passed`, `Backend full proof 98 passed, 3 skipped`

- Full frontend proof surface:

```bash
cd frontend && yarn lint && CI=true yarn test --watch=false --runInBand && yarn build
```

Result: `5 passed test suites`, `14 passed tests`, build passed

## Files Touched

- `hca/src/hca/storage/runs.py`
- `hca/src/hca/runtime/runtime.py`
- `hca/src/hca/api/runtime_actions.py`
- `hca/src/hca/api/run_views.py`
- `backend/server.py`
- `backend/server_models.py`
- `backend/server_status_routes.py`
- `contract/schema.json`
- `backend/tests/test_server_bootstrap.py`
- `backend/tests/test_contract_conformance.py`
- `backend/tests/test_hca.py`
- `hca/tests/unit/test_approval_edge_cases.py`
- `frontend/src/lib/api.js`
- `frontend/src/components/OperatorConsole.js`
- `frontend/src/components/HCAChat.js`
- `frontend/src/lib/api.test.js`
- `frontend/src/components/OperatorConsole.test.js`
- `frontend/src/components/HCAChat.test.js`

## Remaining Work Outside This Pass

- Optional supported-mode proof only: run `RUN_MEMVID_TESTS=1 python scripts/run_tests.py --sidecar` against a healthy local sidecar and separately verify real Mongo-backed `/api/status` behavior if release scope requires those modes.
- Add any release-specific observability or deployment notes separately from this hardening record.
