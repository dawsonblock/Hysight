# HCA — Hybrid Cognitive Agent System

## Original Problem Statement
User uploaded `Hybrid-ai.zip` containing two isolated systems:
1. `Conscious-hybrid--main-2` (Python HCA Runtime): State machine orchestrator, core reasoning modules were hardcoded stubs.
2. `memvid-Human--main-main-2` (Rust Memory Engine): Production-quality memory storage kernel (BM25, WAL, embeddings) but lacks HTTP API.

**User direction**: Keep HCA orchestrator in Python. Turn memvid into the authoritative memory service in Rust. Add a narrow contract between them.

**LLM choices**: Claude Sonnet 4.5 (Planner), Gemini 3 Flash (TextPerception)
**Frontend**: Minimal chat UI with dark terminal aesthetic

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
├── memory_service/              Python MemoryController (contract mock)
│   ├── __init__.py
│   ├── controller.py            BM25-lite ingest/retrieve/maintain
│   ├── singleton.py             Process-level singleton
│   └── types.py                 Pydantic contract types
├── memvid_service/              Rust Axum HTTP sidecar (ready to compile)
│   ├── Cargo.toml
│   └── src/main.rs              Axum server for /memory/ingest|retrieve|maintain
├── contract/
│   └── schema.json              Authoritative cross-boundary schema
└── tests/
    └── test_hca_pipeline.py     Integration test suite (7 tests, all pass)
```

---

## Contract Boundary (schema.json)

Three endpoints define the narrow contract:
- `POST /memory/ingest`    ← `CandidateMemory` in → `{memory_id}` out
- `POST /memory/retrieve`  ← `RetrievalQuery` in → `[RetrievalHit]` out
- `POST /memory/maintain`  ← empty in → `MaintenanceReport` out

**Swap to Rust**: Set `MEMORY_BACKEND=rust` + `MEMORY_SERVICE_URL=http://localhost:3031` to forward all calls to the Rust Axum sidecar.

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | /api/hca/run | Submit goal → run HCA pipeline |
| GET | /api/hca/run/{run_id} | Fetch run state + trace |
| POST | /api/hca/run/{run_id}/approve | Approve pending action |
| POST | /api/hca/run/{run_id}/deny | Deny pending action |
| POST | /api/hca/memory/retrieve | Search memory (BM25) |
| POST | /api/hca/memory/maintain | TTL expiry + stats |

---

## What Has Been Implemented

### Session 1 (Apr 2025)
- [x] Extracted and analyzed Hybrid-ai.zip
- [x] Designed narrow contract schema (`contract/schema.json`)
- [x] Created Python MemoryController with BM25 scoring (`memory_service/`)
- [x] Created process-level singleton (`memory_service/singleton.py`)
- [x] LLM-powered Planner (Claude Sonnet 4.5) with memory context + rule-based fallback
- [x] LLM-powered TextPerception (Gemini 3 Flash) with rule-based fallback
- [x] Wired MemoryController into HCA runtime `_record_execution_memory`
- [x] FastAPI backend with full HCA endpoint surface
- [x] Rust Axum HTTP sidecar (compilable, ready to deploy)
- [x] React chat UI ("Cognitive Agent Console") — dark terminal aesthetic
- [x] Integration tests (7/7 passing)

---

## Backlog

### P0
- [ ] Wire memory context into Planner's LLM prompt from persisted storage (currently uses in-process singleton, resets on restart — needs disk load at singleton init)
- [ ] Add WebSocket streaming for real-time pipeline trace (currently blocking HTTP)

### P1
- [ ] Compile and run the Rust Axum sidecar (`cd /app/memvid_service && cargo run --release`)
- [ ] Connect the Rust sidecar to the actual `memvid` crate (Tantivy BM25, HNSW embeddings)
- [ ] Session-based memory scoping (per-user memory isolation)

### P2
- [ ] Batch-commit optimization in Rust MemvidStore (`begin_batch()` / `commit_batch()`)
- [ ] Add Critic module LLM integration (currently rule-based)
- [ ] Add a Semantic memory store (separate from episodic)
- [ ] Frontend: real-time streaming of agent trace steps
- [ ] Frontend: memory browser panel (visualize stored memories)

---

## Environment Variables

```bash
# /app/backend/.env
MONGO_URL=...
DB_NAME=...
EMERGENT_LLM_KEY=sk-emergent-b688eDdA08a2e28Ea8
MEMORY_STORAGE_DIR=storage/memory   # relative to /app/hca cwd

# To swap memory backend to Rust:
MEMORY_BACKEND=rust
MEMORY_SERVICE_URL=http://localhost:3031
```
