# Deployment Guide

Operational reference for running the Hysight backend stack.

---

## Prerequisites

- Docker ≥ 24 with the Compose plugin (`docker compose version`)
- Or Python 3.11+ for local non-container runs

---

## 1 — Local backend-only mode (default, Python memory)

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
pip install -r backend/requirements-test.txt   # installs all runtime deps + hca
cp .env.example .env
./scripts/run_backend.sh
```

---

## 2 — Local backend + memvid sidecar mode (Rust memory)

```bash
cp .env.example .env          # MEMORY_BACKEND / MEMORY_SERVICE_URL are set by the overlay
docker compose -f compose.yml -f compose.sidecar.yml up --build
```

The overlay (`compose.sidecar.yml`) automatically sets:
- `MEMORY_BACKEND=rust`
- `MEMORY_SERVICE_URL=http://memvid-sidecar:3031`

And adds a `depends_on` so the backend waits for the sidecar to be healthy before starting.

---

## 3 — Test / proof commands

```bash
# smoke proof (no sidecar needed)
make test-bootstrap
make test-pipeline
make test-backend-local

# full backend suite (no sidecar needed)
make test-backend

# sidecar proof (sidecar must be running)
MEMORY_SERVICE_URL=http://localhost:3031 make test-sidecar
```

---

## 4 — Required environment variables

| Variable | Required | Default | Notes |
|---|---|---|---|
| `EMERGENT_LLM_KEY` | yes (for agent runs) | — | LLM API key |
| `MEMORY_BACKEND` | no | `python` | `python` or `rust` |
| `MEMORY_SERVICE_URL` | when `rust` | — | e.g. `http://localhost:3031` |
| `HCA_STORAGE_ROOT` | no | `<repo>/storage` | Run storage path |
| `MEMORY_STORAGE_DIR` | no | `<repo>/storage/memory` | Memory store path |
| `MONGO_URL` | paired with `DB_NAME` | — | Set both or neither |
| `DB_NAME` | paired with `MONGO_URL` | — | Set both or neither |
| `CORS_ORIGINS` | no | (none) | Comma-separated origins |

See `.env.example` for the full annotated template.

---

## 5 — Health check URLs

| Service | URL | Expected response |
|---|---|---|
| Backend | `http://localhost:8000/api/` | `{"message":"HCA API — Hybrid Cognitive Agent"}` |
| Memvid sidecar | `http://localhost:3031/health` | `{"status":"ok",...}` |

```bash
# backend
curl http://localhost:8000/api/

# sidecar (when running)
curl http://localhost:3031/health
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

### `BackendConfigurationError: Mongo configuration is partial`
Set **both** `MONGO_URL` and `DB_NAME`, or unset both. Mixed state is rejected at startup.

### `MemoryConfigurationError: MEMORY_SERVICE_URL is required`
`MEMORY_BACKEND=rust` was set but `MEMORY_SERVICE_URL` was not. Either switch back to `MEMORY_BACKEND=python` or start the sidecar and set the URL.

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
