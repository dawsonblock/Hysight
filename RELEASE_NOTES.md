# Release Notes

This release consolidates the backend authority path, formalizes replay-backed
operator health visibility, and keeps optional deployment modes explicit rather
than coupling them to the default local proof surface.

## Observability

- `GET /api/subsystems` is the release-facing operator health endpoint.
- The endpoint is always available, even when optional integrations are not.
- Subsystem reporting is split by `database`, `memory`, `storage`, `llm`,
  and the bounded `autonomy` control plane for degraded-mode diagnosis.
- The autonomy surface now exposes kill-switch state, pending escalations,
  recent active run links, per-agent budget ledgers, the last evaluator
  decision, and the latest checkpoint summary without creating a second
  execution authority.
- `POST /api/status` and `GET /api/status` remain optional and intentionally
  return `503` when Mongo-backed persistence is not configured.

## Subsystem Health

- `database`
  - `disabled` when `MONGO_URL` and `DB_NAME` are unset.
  - `healthy` when Mongo-backed `/api/status` persistence is reachable.
  - `unhealthy` when Mongo is configured but the backend client is unavailable
    or ping fails.
- `memory`
  - `healthy` in the default python-backed mode.
  - `healthy` in Rust sidecar mode only when `/health` succeeds.
  - `unhealthy` when sidecar mode is configured but unreachable or invalid.
- `storage`
  - Reports whether the HCA storage root and memory storage are writable.
- `llm`
  - Reports whether `EMERGENT_LLM_KEY` is configured.

## Deployment Notes

- The default supported local mode remains:
  - python in-process memory
  - no required Mongo instance
  - no required Rust sidecar
- Mongo-backed `/api/status` persistence remains an explicit optional mode.
  - Configure both `MONGO_URL` and `DB_NAME`, or leave both unset.
  - Partial Mongo configuration fails fast at startup.
- Rust memvid sidecar mode remains an explicit optional mode.
  - Configure `MEMORY_BACKEND=rust` and a healthy `MEMORY_SERVICE_URL`.
  - Backend startup validates the sidecar via `/health` and fails fast when it
    is unreachable.
- Credentialed browser access remains fail-closed.
  - `CORS_ORIGINS` must be an explicit comma-separated allowlist of absolute
    origins.
- The repo root is now an honest workspace/meta-project.
  - `python -m pip install -e '.[dev]'` at the root installs tooling only.
  - The supported runtime/bootstrap path remains `make venv`, which installs editable `./hca` through `backend/requirements-test.txt`.
- Proof receipts now land under `artifacts/proof/`, with timestamped live
  history receipts under `artifacts/proof/history/` for the live Mongo and
  live sidecar harnesses.
- Aggregate receipts now declare `covered_proof_steps` and
  `omitted_proof_steps`, and frontend receipts declare the exact covered stage
  names so proof claims stay scoped to what actually ran.

## Proof Commands

- Default local proof surface:

```bash
python scripts/run_tests.py
```

Current enforced baseline contract in the runner:

- HCA pipeline proof: `7 passed`
- Backend baseline proof: `98 passed, 1 deselected`
- Contract conformance proof: `18 passed`
- Overall baseline proof: `123 passed, 0 skipped`
- Autonomy optional proof: `50 passed, 0 skipped`

## Release Seal Status for Hysight-main 31 (2026-04-19)

- Release verdict: `sealed full-proof release`
- Packaging install passed fresh from a clean copied tree for this exact revision.
- `make venv` passed fresh from the same clean tree.
- `.pkg-venv` did not contaminate the supported proof path.
- Fresh optional evidence counted in this seal: live Rust sidecar, live parity, fail-closed no-fallback behavior, and frontend proof on Node 20.20.2 / Yarn 1.22.22.
- Live Mongo was not rerun in this seal and remains historical only.
- Historical Hysight 28 and 29 summary files remain in the tree for audit context only and are not proof for 31.

- Optional frontend proof:

```bash
make test-bootstrap-frontend
make proof-frontend
```

- Optional live Rust sidecar proof:

```bash
make run-memvid-sidecar
make proof-sidecar
```

- Optional live Rust sidecar proof on an alternate localhost port:

```bash
MEMORY_SERVICE_PORT=3032 make run-memvid-sidecar
MEMORY_SERVICE_PORT=3032 make proof-sidecar
```

- Optional live Mongo-backed `/api/status` proof:

```bash
make proof-mongo-live
```

- Release-seal optional evidence for Hysight-main 31 on 2026-04-19 was refreshed with:

```bash
make proof-sidecar
python scripts/proof_frontend.py
python -m pytest backend/tests/test_memvid_sidecar_parity.py -q --run-live -ra --strict-markers
```

- The sidecar harness now falls forward to the next free localhost port when
  the default `http://localhost:3031` target is occupied or unhealthy, so the
  default `make proof-sidecar` path can still complete on hosts where `3031`
  is reserved by another local listener.

- Live Mongo support remains available, but Mongo receipts were not regenerated
  during this seal pass and are therefore historical only.

Narrow already-running-Mongo path when you do not want the disposable harness:

```bash
make test-mongo-live
```

Override the connection target when needed:

```bash
LIVE_MONGO_URL=mongodb://127.0.0.1:27017 \
LIVE_MONGO_DB_NAME=hysight_live \
make test-mongo-live
```

## Current Limitations

- Optional live Mongo and live Rust sidecar modes are supported, but remain
  explicit opt-in proof surfaces rather than part of the default service-free
  local proof path.
- The frontend operator surface is still JavaScript-first and does not yet have
  a full static TypeScript migration.
- `backend/server.py` is now an adapter layer, but the backend refactor should
  still receive dedicated verification before release sign-off.
