# HCA — Hybrid Cognitive Agent System

## Original Problem Statement
User uploaded `Hybrid-ai.zip` containing two isolated systems:
1. `Conscious-hybrid--main-2` (Python HCA Runtime): State machine orchestrator with hardcoded stubs.
2. `memvid-Human--main-main-2` (Rust Memory Engine): Production memory kernel (BM25, WAL) lacking HTTP API.

**User direction**: Keep HCA orchestrator in Python. Turn memvid into the authoritative memory service in Rust. Add a narrow contract between them.

**LLM choices**: Claude Sonnet 4.5 (Planner), Gemini 3 Flash (TextPerception)
**Frontend**: Minimal chat UI with white theme

---

## Architecture

```
/app/
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
├── memvid_service/              Rust Axum HTTP sidecar (production memory layer)
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
|--------|------|-------------|
| POST | /memory/ingest | CandidateMemory → {memory_id} |
| POST | /memory/retrieve | RetrievalQuery → [RetrievalHit] (Tantivy BM25 scored) |
| POST | /memory/maintain | TTL expiry → MaintenanceReport |
| GET | /memory/list | Paginated record list |
| DELETE | /memory/:id | Hard delete (persisted in deleted_ids.txt) |
| GET | /health | Liveness check → {"status":"ok","engine":"tantivy-bm25"} |

**Backend switch**: `MEMORY_BACKEND=rust` + `MEMORY_SERVICE_URL=http://localhost:3031`

---

## Python API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | /api/hca/run | Submit goal → HCA pipeline result |
| GET | /api/hca/run/{run_id} | Fetch run state + trace |
| POST | /api/hca/run/{run_id}/approve | Approve pending action |
| POST | /api/hca/run/{run_id}/deny | Deny pending action |
| POST | /api/hca/run/stream | SSE streaming pipeline trace |
| POST | /api/hca/memory/retrieve | BM25 search |
| POST | /api/hca/memory/maintain | TTL expiry |
| GET | /api/hca/memory/list | List memories |
| DELETE | /api/hca/memory/{id} | Delete memory |

---

## What Has Been Implemented

### Session 1 (Apr 2025)
- [x] Extracted and analyzed Hybrid-ai.zip
- [x] Designed narrow contract schema (`contract/schema.json`)
- [x] Created Python MemoryController with BM25 scoring (`memory_service/`)
- [x] LLM-powered Planner (Claude Sonnet 4.5) + TextPerception (Gemini 3 Flash)
- [x] Wired MemoryController into HCA runtime `_record_execution_memory`
- [x] FastAPI backend with full HCA endpoint surface
- [x] Rust Axum HTTP sidecar (compilable, ready to deploy)
- [x] React chat UI ("Cognitive Agent Console") — dark terminal aesthetic
- [x] Integration tests (7/7 passing)

### Session 2 (Apr 2025)
- [x] White background theme with larger text
- [x] SSE streaming endpoint `POST /api/hca/run/stream`
- [x] Frontend live-streaming trace via ReadableStream
- [x] Markdown renderer (`react-markdown` + `remark-gfm`)

### Session 3 (Apr 2025)
- [x] Installed Rust; compiled Axum sidecar
- [x] Added `GET /memory/list` and `DELETE /memory/:id`
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
- [x] 14/15 backend tests pass (iteration_3.json)

---

## Backlog

### P1
- [ ] Add Critic module LLM integration (currently rule-based in Python HCA)
- [ ] Session/user-scoped memory isolation (per-user memory partition)

### P2
- [ ] Semantic memory store using HNSW (separate from episodic traces)
- [ ] Batch-commit optimization in Rust sidecar
- [ ] Frontend: MemoryBrowser to show real-time Tantivy search scores

---

## Environment Variables

```bash
# /app/backend/.env
MONGO_URL=mongodb://localhost:27017
DB_NAME=test_database
EMERGENT_LLM_KEY=sk-emergent-b688eDdA08a2e28Ea8
MEMORY_BACKEND=rust
MEMORY_SERVICE_URL=http://localhost:3031
MEMORY_STORAGE_DIR=storage/memory

# /app/memvid_service (via supervisor env)
MEMORY_SERVICE_PORT=3031
MEMORY_DATA_DIR=/app/memvid_service/data
RUST_LOG=info
```

---

## Rust Sidecar Notes

- Binary: `/app/memvid_service/target/release/memvid-sidecar`
- Managed by: `sudo supervisorctl restart memvid-sidecar`
- Logs: `/var/log/supervisor/memvid-sidecar.{out,err}.log`
- Rebuild: `cd /app/memvid_service && ~/.cargo/bin/cargo build --release`
- Data: `/app/memvid_service/data/memory.mv2` (WAL + Tantivy index)
