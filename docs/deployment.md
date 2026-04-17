# Deployment Guide

Operational reference for running the Hysight backend stack.

The canonical public HTTP surface is `backend.server:app`, exposed through `./scripts/run_backend.sh` locally or `docker compose up --build` in containers. The FastAPI app in `hca/src/hca/api/app.py` is an internal compatibility surface for repo-local tests; it is not a deployment or frontend entrypoint.

The default memory mode is the in-process Python backend (`MEMORY_BACKEND=python`). The Rust memvid sidecar is optional and only changes the memory implementation behind the backend; it does not replace the public HTTP API.

When `MEMORY_BACKEND=python`, `MEMORY_SERVICE_URL` must be unset. When
`MEMORY_STORAGE_DIR` is set, it must be an absolute child path under
`HCA_STORAGE_ROOT`.

---

## Prerequisites

- Docker ≥ 24 with the Compose plugin (`docker compose version`)
- Or Python 3.11+ in a repo-local virtual environment for local non-container runs

The Python runtime package lives under `./hca` and is installed editable as part of repo bootstrap.

---

## 1 — Local backend-only mode (default public API, Python memory)

### Container

```bash
cp .env.example .env          # fill in EMERGENT_LLM_KEY at minimum
docker compose up --build
```

Backend is ready when the healthcheck passes:

```bash
curl http://localhost:8000/api/
# → {"message":"HCA API — Hybrid Cognitive Agent"}
```

### Without containers

```bash
make venv
source .venv/bin/activate
make test-bootstrap
cp .env.example .env
./scripts/run_backend.sh
```

This starts the public backend app. Do not deploy `hca.api.app:app` for normal local or container-backed usage.
The launcher now resolves and exports `MEMORY_BACKEND`, `HCA_STORAGE_ROOT`,
and `MEMORY_STORAGE_DIR` explicitly before starting uvicorn, then prints the
active memory mode and storage roots. It now also rejects mixed python+sidecar
config and storage paths that are relative or outside the configured
`HCA_STORAGE_ROOT`.

---

## 2 — Optional backend + memvid sidecar mode (public API unchanged)

```bash
cp .env.example .env          # MEMORY_BACKEND / MEMORY_SERVICE_URL are set by the overlay
docker compose -f compose.yml -f compose.sidecar.yml up --build
```

The overlay (`compose.sidecar.yml`) automatically sets:

- `MEMORY_BACKEND=rust`
- `MEMORY_SERVICE_URL=http://memvid-sidecar:3031`
- `MEMORY_DATA_DIR=/app/data`

And adds a `depends_on` so the backend waits for the sidecar to be healthy before starting.

The frontend and operator APIs still talk to the same backend routes (`/api/...` and `/api/hca/...`). Only the backing memory implementation changes.

---

## 3 — Test / proof commands

```bash
# canonical local proof wrapper
./scripts/proof_local.sh

# frontend operator proof bootstrap + wrapper
make test-bootstrap-frontend
make proof-frontend

# create and use the repo-local virtual environment
make venv
source .venv/bin/activate

# install the default local proof surface
make test-bootstrap

# optional integration/live Mongo proof dependencies
make test-bootstrap-integration

# default service-free local proof surface
make test

# individual baseline proof components
make test-pipeline
make test-contract
make test-backend-baseline

# optional mock-backed backend integration proof (no live sidecar needed)
make test-backend-integration

# sidecar proof (sidecar must be running; default port is 3031)
make proof-sidecar
make test-sidecar

# if localhost:3031 is occupied, override the local sidecar port
MEMORY_SERVICE_PORT=3032 make run-memvid-sidecar
MEMORY_SERVICE_PORT=3032 make test-sidecar
MEMORY_SERVICE_PORT=3032 make proof-sidecar

# live Mongo-backed /api/status proof
make proof-mongo-live
make test-mongo-live

# override the live Mongo connection when needed
LIVE_MONGO_URL=mongodb://127.0.0.1:27017 \
LIVE_MONGO_DB_NAME=hysight_live \
make test-mongo-live
```

`python scripts/run_tests.py` now runs each proof step with an isolated
temporary `HCA_STORAGE_ROOT` and matching `MEMORY_STORAGE_DIR`, so proof does
not rely on repo-default storage state.

Generated receipts now declare exactly which proof steps they cover via
`covered_proof_steps` and `omitted_proof_steps`. Frontend receipts also declare
their covered stage names so lint, Jest, build, and fixture-drift claims stay
explicit.

The default local proof surface is `make test` / `python scripts/run_tests.py`.
The frontend, backend integration, live Mongo, and live sidecar proofs are
separate opt-in tiers.

If you use the repo-scoped VS Code verification workflow, prepare
`test_result.md` first with
`.github/prompts/prepare-verification-handoff.prompt.md`, then hand backend or
frontend verification to the corresponding agent under `.github/agents/`.

---

## 4 — Required environment variables

| Variable | Required | Default | Notes |
| --- | --- | --- | --- |
| `EMERGENT_LLM_KEY` | yes (for agent runs) | — | LLM API key |
| `MEMORY_BACKEND` | no | `python` | `python` or `rust` |
| `MEMORY_SERVICE_URL` | when `rust` | — | Must be unset in `python` mode |
| `HCA_STORAGE_ROOT` | no | `<repo>/storage` | Run storage path |
| `MEMORY_STORAGE_DIR` | no | `<HCA_STORAGE_ROOT>/memory` | Absolute child path under `HCA_STORAGE_ROOT` |
| `MONGO_URL` | paired with `DB_NAME` | — | Set both or neither |
| `DB_NAME` | paired with `MONGO_URL` | — | Set both or neither |
| `CORS_ORIGINS` | no | (none) | Comma-separated origins |

See `.env.example` for the full annotated template.

---

## 5 — Health check URLs

| Service | URL | Expected response |
| --- | --- | --- |
| Backend | `http://localhost:8000/api/` | `{"message":"HCA API — Hybrid Cognitive Agent"}` |
| Memvid sidecar | `http://localhost:<MEMORY_SERVICE_PORT>/health` (default `3031`) | `{"status":"ok",...}` |

```bash
# backend
curl http://localhost:8000/api/

# sidecar (when running; default port is 3031)
curl "${MEMORY_SERVICE_URL:-http://localhost:3031}/health"
```

---

## 6 — Container build commands (standalone)

```bash
# backend image only
docker build -f backend/Dockerfile -t hysight-backend .

# sidecar image only (build context must be repo root)
docker build -f memvid_service/Dockerfile -t hysight-sidecar .
```

---

## 7 — Common failure cases

### Container user and volume permissions

Both containers run as a non-root system user (`hysight`). The only directory
that requires write access is mounted as a named volume:

| Container | Mount path | Volume name |
| --- | --- | --- |
| `backend` | `/app/storage` | `hca-storage` |
| `memvid-sidecar` | `/app/data` | `sidecar-data` |

Docker initialises named volumes by copying the container's existing directory
content (which is already owned by `hysight`), so no manual `chown` step is
needed for compose-managed deployments.

If you bind-mount a host directory instead of using a named volume, ensure the
host directory is writable by the UID assigned to the `hysight` system user
inside the container. You can check it with:

```bash
docker run --rm hysight-backend id -u hysight
```

Then on the host:

```bash
chown -R <uid>:<uid> /your/host/path
```

### `BackendConfigurationError: Mongo configuration is partial`

Set **both** `MONGO_URL` and `DB_NAME`, or unset both. Mixed state is rejected at startup.

### `MemoryConfigurationError: MEMORY_SERVICE_URL is required`

`MEMORY_BACKEND=rust` was set but `MEMORY_SERVICE_URL` was not. Either switch back to `MEMORY_BACKEND=python` or start the sidecar and set the URL.

### `MemoryConfigurationError: MEMORY_SERVICE_URL must be unset unless MEMORY_BACKEND=rust`

Remove `MEMORY_SERVICE_URL` in python mode, or switch fully to sidecar mode by setting `MEMORY_BACKEND=rust`.

### `MemoryConfigurationError: MEMORY_STORAGE_DIR must be inside HCA_STORAGE_ROOT`

Set `MEMORY_STORAGE_DIR` to an absolute child directory such as `<HCA_STORAGE_ROOT>/memory`.

### `MemoryConfigurationError: Rust memory backend health check failed`

The sidecar URL is set but the sidecar is not reachable. Verify the sidecar is running:

```bash
curl http://localhost:3031/health
```

If using compose, check `docker compose logs memvid-sidecar`.

### `BackendConfigurationError: CORS_ORIGINS cannot contain '*'`

Replace `*` with a specific origin list, e.g. `http://localhost:3000`.

### Backend container exits immediately

Check logs: `docker compose logs backend`. Common causes: missing `EMERGENT_LLM_KEY`, bad `MONGO_URL`, or sidecar not ready (in sidecar mode).

### `ERROR: memory_service package not found` (local mode)

Run from the repo root after installing deps:

```bash
pip install -r backend/requirements-test.txt
./scripts/run_backend.sh
```
