# Release Notes

This release consolidates the backend authority path, formalizes replay-backed
operator health visibility, and keeps optional deployment modes explicit rather
than coupling them to the default local proof surface.

## Observability

- `GET /api/subsystems` is the release-facing operator health endpoint.
- The endpoint is always available, even when optional integrations are not.
- Subsystem reporting is split by `database`, `memory`, `storage`, and `llm`,
  each with status detail for degraded-mode diagnosis.
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

## Proof Commands

- Default local proof surface:

```bash
python scripts/run_tests.py
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