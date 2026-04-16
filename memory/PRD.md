# HCA — Hybrid Cognitive Agent System

> Historical migration and design notes from Apr 2025.
> This file is not the current operational source of truth.
> For current runtime behavior use `README.md`, `backend/.env.example`, `backend/server.py`, and `contract/schema.json`.
> Current sidecar data roots are env-driven and untracked; do not treat the historical `data/` paths below as seeded runtime state.

## Original Problem Statement

User uploaded `Hybrid-ai.zip` containing two isolated systems:

1. `Conscious-hybrid--main-2` (Python HCA Runtime): State machine orchestrator with hardcoded stubs.
2. `memvid-Human--main-main-2` (Rust Memory Engine): Rust memory kernel (BM25, WAL) lacking HTTP API.

**User direction**: Keep HCA orchestrator in Python. Turn memvid into the authoritative memory service in Rust. Add a narrow contract between them.

**LLM choices**: Claude Sonnet 4.5 (Planner), Gemini 3 Flash (TextPerception)
**Frontend**: Minimal chat UI with white theme

---

## Architecture

```text
Hysight/
├── backend/                     FastAPI server — HCA API surface
├── frontend/                    React chat UI ("Cognitive Agent Console")
├── hca/                         Python HCA orchestrator (installed package)
│   └── src/hca/
│       ├── runtime/runtime.py   State machine + MemoryController integration
│       ├── modules/planner.py   LLM-powered (Claude Sonnet 4.5)
│       ├── modules/perception_text.py  LLM-powered (Gemini 3 Flash)
│       └── storage/             Run events, receipts, approvals (JSONL)
├── memory_service/              Python MemoryController (contract fallback)
├── memvid/                      memvid-core Rust library (Tantivy BM25 + WAL)
├── memvid_service/              Optional Rust Axum HTTP sidecar
│   ├── Cargo.toml               (depends on memvid-core, features = ["lex"])
│   ├── src/main.rs              PersistentMemoryStore + Axum routes
│   └── data/
│       ├── memory.mv2           WAL + Tantivy BM25 index (persistent)
│       └── deleted_ids.txt      Append-only deletion log (persistent)
├── contract/
│   └── schema.json              Authoritative cross-boundary schema
└── tests/
    └── test_hca_pipeline.py     Integration test suite
```

---

## Contract Boundary (schema.json)

| Method | Path | Description |
| --- | --- | --- |
| POST | /memory/ingest | CandidateMemory → {memory_id} |
| POST | /memory/retrieve | RetrievalQuery → [RetrievalHit] (Tantivy BM25 scored) |
| POST | /memory/maintain | TTL expiry → MaintenanceReport |
| GET | /memory/list | Paginated record list |
| DELETE | /memory/{memory_id} | Hard delete |
| GET | /health | Liveness check |

**Current backend switch**: `MEMORY_BACKEND=rust` + `MEMORY_SERVICE_URL=http://localhost:3031`

---

## Python API Endpoints

| Method | Path | Description |
| --- | --- | --- |
| POST | /api/hca/run | Submit goal → HCA pipeline result |
| GET | /api/hca/run/{run_id} | Fetch run state + trace |
| POST | /api/hca/run/{run_id}/approve | Approve pending action |
| POST | /api/hca/run/{run_id}/deny | Deny pending action |
| POST | /api/hca/run/stream | SSE streaming pipeline trace |
| POST | /api/hca/memory/retrieve | BM25 search |
| POST | /api/hca/memory/maintain | TTL expiry |
| GET | /api/hca/memory/list | List memories |
| DELETE | /api/hca/memory/{memory_id} | Delete memory |

---

## What Has Been Implemented

This section is a historical implementation log from the original migration work. It is not a current status dashboard.

### Session 1 (Apr 2025)

- [x] Extracted and analyzed Hybrid-ai.zip
- [x] Designed narrow contract schema (`contract/schema.json`)
- [x] Created Python MemoryController with BM25 scoring (`memory_service/`)
- [x] LLM-powered Planner (Claude Sonnet 4.5) + TextPerception (Gemini 3 Flash)
- [x] Wired MemoryController into HCA runtime `_record_execution_memory`
- [x] FastAPI backend with full HCA endpoint surface
- [x] Rust Axum HTTP sidecar (compilable at that stage)
- [x] React chat UI ("Cognitive Agent Console")
- [x] Integration tests added

### Session 2 (Apr 2025)

- [x] White background theme with larger text
- [x] SSE streaming endpoint `POST /api/hca/run/stream`
- [x] Frontend live-streaming trace via ReadableStream
- [x] Markdown renderer (`react-markdown` + `remark-gfm`)

### Session 3 (Apr 2025)

- [x] Installed Rust; compiled Axum sidecar
- [x] Added `GET /memory/list` and `DELETE /memory/{memory_id}`
- [x] Migrated 15 JSONL memories to Rust store; swapped to `MEMORY_BACKEND=rust`
- [x] MemoryBrowser panel in frontend

### Session 4 (Apr 2025)

- [x] **Connected memvid-core crate** (Tantivy BM25 + WAL) to the Axum sidecar
  - Dependency: `memvid-core = { path = "../memvid", default-features = false, features = ["lex"] }`
  - Replaced handcrafted BM25 with real Tantivy search engine
- [x] **Full WAL persistence**: memories stored in `data/memory.mv2` survive sidecar restarts
- [x] **Deletion persistence**: deleted IDs written to `data/deleted_ids.txt`
- [x] Startup frame scan: rebuilds in-memory HashMap from `.mv2` frames on boot
- [x] Added `/health` endpoint for liveness checks
- [x] Fixed DELETE 404 for non-existent IDs
- [x] Added supervisor config (`supervisord_sidecar.conf`) for auto-restart
- [x] Expanded backend proof coverage during that phase

---

## Historical Backlog Note

The backlog from this migration document is no longer authoritative. Use the current repository state and issue tracker for live planning.

---

## Environment Variables

```bash
# backend/.env
MONGO_URL=mongodb://localhost:27017
DB_NAME=hysight
# EMERGENT_LLM_KEY=...
MEMORY_BACKEND=rust
MEMORY_SERVICE_URL=http://localhost:3031
MEMORY_STORAGE_DIR=storage/memory

# memvid_service environment
MEMORY_SERVICE_PORT=3031
MEMORY_DATA_DIR=./data
RUST_LOG=info
```

For current examples, prefer `backend/.env.example` over this historical snapshot.

---

## Rust Sidecar Notes

- Binary: `memvid_service/target/release/memvid-sidecar`
- Rebuild: `cd memvid_service && cargo build --release`
- Optional process management can be done with supervisor or another service manager, but that is deployment-specific.
- Data directory defaults to `memvid_service/data/` unless overridden with `MEMORY_DATA_DIR`.
