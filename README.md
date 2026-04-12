# Hysight — Hybrid Cognitive Agent

*A bounded cognitive runtime that thinks, plans, critiques, and acts — with human approval built in.*

[![Python](https://img.shields.io/badge/python-3.9%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)](https://react.dev/)
[![MongoDB](https://img.shields.io/badge/MongoDB-Motor%203.3-47A248?logo=mongodb&logoColor=white)](https://www.mongodb.com/)
[![Rust](https://img.shields.io/badge/Rust-Axum%200.7-CE412B?logo=rust&logoColor=white)](https://www.rust-lang.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Quick start

```bash
# 1. Install backend test dependencies
python -m pip install -r backend/requirements-test.txt

# 2. Run the full default proof surface
python scripts/run_tests.py

# 3. Optional — live sidecar proof (requires running memvid sidecar)
RUN_MEMVID_TESTS=1 python scripts/run_tests.py --sidecar
```

That is the only command you need to verify the system locally.
Everything else below is full setup, configuration, and advanced use.

---

## Overview

Hysight is an implementation of a **Hybrid Cognitive Agent (HCA)** as a bounded operator runtime. Its authority path stays inside the existing runtime, approval, executor, and replay layers instead of handing control to an open-ended autonomous loop. The cognitive modules (Planner, Critic, Perception, ToolReasoner) still compete for space in a capacity-limited **Global Workspace**, but they can only propose actions that the registry and executor actually implement.

The runtime currently executes one canonical action per run through a single authority path in `hca/src/hca/runtime/runtime.py`, with approval-bound resume for mutating actions, immutable event logging, snapshots, receipts, artifacts, and replay reconstruction. Practical repo work comes from a small bounded tool catalog for inspection, reporting, and approved mutation rather than speculative autonomy.

---

## Architecture

```text
┌─────────────────────────────────────────────────────────┐
│                      HCA Runtime                        │
│                                                         │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐  ┌──────┐  │
│  │ Planner  │  │  Critic  │  │Perception │  │ Tool │  │
│  │ (LLM)   │  │(LLM+Rule)│  │  (Text)   │  │Rsner │  │
│  └────┬─────┘  └────┬─────┘  └─────┬─────┘  └──┬───┘  │
│       │             │              │             │      │
│       └─────────────┴──────────────┴─────────────┘      │
│                          │                              │
│               ┌──────────▼──────────┐                  │
│               │  Global Workspace   │  ← capacity: 7   │
│               │  (scored + ranked)  │                  │
│               └──────────┬──────────┘                  │
│                          │                              │
│               ┌──────────▼──────────┐                  │
│               │   Meta Monitor      │                  │
│               │  conflict detect    │                  │
│               │  missing-info scan  │                  │
│               │  confidence track   │                  │
│               └──────────┬──────────┘                  │
│                          │                              │
│               ┌──────────▼──────────┐                  │
│               │  Action Scoring     │                  │
│               │  risk / reversibil. │                  │
│               └──────────┬──────────┘                  │
│                          │                              │
│          ┌───────────────▼───────────────┐             │
│          │      Approval Gate            │             │
│          │  registry policy + approval   │             │
│          └───────────────┬───────────────┘             │
│                          │                              │
│               ┌──────────▼──────────┐                  │
│               │     Executor        │                  │
│               │  tool call + audit  │                  │
│               └──────────┬──────────┘                  │
│                          │                              │
│               ┌──────────▼──────────┐                  │
│               │   Memory Commit     │                  │
│               │  episodic / semantic│                  │
│               └─────────────────────┘                  │
└─────────────────────────────────────────────────────────┘
         │                            │
  ┌──────▼──────┐            ┌────────▼────────┐
  │  FastAPI    │            │  memvid-sidecar  │
  │  Backend    │            │  (Rust / Axum)   │
  └──────┬──────┘            └─────────────────┘
         │
  ┌──────▼──────┐
  │  React 19   │
  │  Frontend   │
  └─────────────┘
```

---

## Key Features

| Feature | Description |
| --- | --- |
| **Global Workspace** | Capacity-limited (7 slots) item-ranked workspace inspired by Global Workspace Theory |
| **Optional LLM Modules** | Planner, Critic, and TextPerception can use external LLMs when configured and fall back to deterministic behavior when unavailable |
| **Approval Gate** | Approval is defined centrally in the tool registry. Read-only workspace inspection tools execute directly; mutation and other configured side effects require explicit approval and resume with the same canonical action binding. |
| **Immutable Event Log** | Every state transition, proposal, and execution is appended to an append-only JSONL log |
| **Conflict Detection** | Automatic detection of contradicting action proposals across modules |
| **Bounded Tool Catalog** | Repo-bounded tools now cover stat, glob, search, targeted text reads, investigation reports, run reports, approved text patching, artifact writes, and an allowlisted command path |
| **Memory Outcomes** | Local episodic memory writes are authoritative. External memory-controller ingestion remains best-effort, but success and failure are now emitted explicitly in the event log. |
| **Evaluation Harnesses** | Six built-in harnesses: audit, coordination, embodiment, memory, metacognition, proactivity |
| **Portable Storage** | All paths resolve from repo root; override via `HCA_STORAGE_ROOT` env var |
| **Memvid Sidecar** | Rust/Axum HTTP sidecar exposing the `ingest / retrieve / maintain` memory contract |

## Bounded Tool Catalog

The executor registry is the authoritative capability surface. The runtime and planner should only rely on tools that appear there.

Current bounded tools:

- `echo`
- `list_dir`
- `stat_path`
- `glob_workspace`
- `search_workspace`
- `read_text_range`
- `read_file` (legacy alias for `read_text_range`)
- `investigate_workspace_issue`
- `create_run_report`
- `patch_text_file`
- `replace_in_file` (legacy alias for `patch_text_file`)
- `store_note`
- `write_artifact`
- `run_command` (allowlisted only; no shell)

Mutation and reporting behavior:

- `patch_text_file` binds approval to the canonical validated action plus a file-state hash before execution.
- Successful patch actions emit before/after hashes, changed-line summaries, and a diff artifact.
- `create_run_report` materializes a deterministic artifact from prior events, receipts, approvals, artifacts, and memory outcomes for a run.
- `investigate_workspace_issue` is a bounded read-only workflow tool that searches, reads targeted ranges, and emits a structured evidence artifact.

Replay and memory guarantees:

- Replay and resume validate canonical action identity against approval bindings before consuming approval.
- Local episodic memory writes are part of the normal runtime path.
- External memory-controller ingestion is best-effort, but emits `external_memory_written` or `external_memory_write_failed` events instead of failing silently.
- Command execution, when used, stays bounded to allowlisted argument arrays, repo-relative cwd, timeouts, and truncated output.

---

## Repository Structure

```text
Hysight/
├── hca/                        # Core cognitive agent package
│   ├── src/hca/
│   │   ├── api/                # FastAPI sub-application (runs, eval, memory, admin)
│   │   ├── cli/                # CLI entry points (smoke, eval, replay)
│   │   ├── common/             # Shared enums, types, time utilities
│   │   ├── evaluation/         # Evaluation harnesses and metrics
│   │   ├── executor/           # Approval enforcement + tool registry
│   │   ├── memory/             # Episodic, semantic, procedural, identity stores
│   │   ├── meta/               # Conflict detection, missing-info scan, self-model
│   │   ├── modules/            # Cognitive modules: Planner, Critic, Perception, ToolReasoner
│   │   ├── paths.py            # Centralized, repo-relative path resolver
│   │   ├── prediction/         # Action scoring and ranking
│   │   ├── runtime/            # Orchestrator, state machine, replay, snapshots
│   │   ├── storage/            # Run state, event log, receipts, artifacts, approvals
│   │   └── workspace/          # Global Workspace: admission, broadcast, ranking, recurrence
│   ├── configs/                # YAML configuration (base, models, policy, safety, memory)
│   └── tests/                  # Unit and integration test suites
│
├── backend/                    # FastAPI HTTP server + MongoDB integration
│   ├── server.py               # Application factory, settings, lifecycle, routes
│   └── tests/                  # Backend unit and integration tests
│
├── frontend/                   # React 19 single-page application
│   ├── src/                    # Components, pages, hooks, API client
│   └── public/                 # Static assets
│
├── memory_service/             # Optional in-process memory controller (Python)
├── memvid/                     # Memvid memory engine bindings
├── memvid_service/             # Memvid HTTP sidecar (Rust / Axum)
├── storage/                    # Runtime-generated run state (gitignored)
└── tests/                      # Top-level integration tests
```

---

## Tech Stack

### Backend / Agent

- Python 3.9+, FastAPI 0.110, Pydantic v2
- Motor 3.3 (async MongoDB driver)
- PyYAML for configuration
- `python-dotenv` for environment management

### Frontend

- React 19, React Router v7
- shadcn/ui (Radix UI primitives + Tailwind CSS)
- Recharts for data visualization
- Axios for HTTP

### Sidecar

- Rust (edition 2021), Axum 0.7, Tokio

### Tooling

- pytest, httpx for testing
- black, isort, flake8, mypy for code quality

---

## Prerequisites

- Python 3.9+
- Node.js 18+ and Yarn 1
- MongoDB 6+ if you want the optional `/api/status` persistence endpoints
- Rust toolchain (only required to build the `memvid-sidecar`)

---

## Installation

### 1. Clone and enter the repository

```bash
git clone https://github.com/dawsonblock/Hysight.git
cd Hysight
```

### 2. Set up the Python environment

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
```

### 3. Bootstrap the proof surface

The shortest supported setup path is:

```bash
make test-bootstrap
```

If you do not want to use `make`, the equivalent command is:

```bash
python -m pip install -r backend/requirements-test.txt
```

That single install command covers:

- the editable `hca` package
- backend runtime dependencies
- backend test dependencies such as `requests-mock`

If you also want formatter, lint, and type-check tooling, use:

```bash
make dev-bootstrap
```

Or, without `make`:

```bash
python -m pip install -r backend/requirements-dev.txt
```

If you only need the backend runtime and not the proof surface:

```bash
python -m pip install -e ./hca -r backend/requirements.txt
```

### 4. Configure environment variables

```bash
cp backend/.env.example backend/.env   # fill in values before starting
```

Edit `backend/.env`:

```dotenv
# Optional — MongoDB connection
# If both values are omitted, the backend starts in local mode and `/api/status`
# returns 503. If either value is set without the other, startup fails.
MONGO_URL=mongodb://localhost:27017
DB_NAME=hysight

# Optional — override where run artifacts are written
# HCA_STORAGE_ROOT=/path/to/custom/storage

# Optional — enable the Rust memory sidecar.
# If MEMORY_BACKEND=rust is set, MEMORY_SERVICE_URL must point to a healthy
# sidecar that responds on /health or startup will fail.
# MEMORY_BACKEND=rust
# MEMORY_SERVICE_URL=http://localhost:3031

# Optional — credentialed browser access.
# CORS is fail-closed by default; use absolute origins only.
# CORS_ORIGINS=http://localhost:3000

# Optional — LLM API key for the Critic module
# EMERGENT_LLM_KEY=...
```

### 5. Install the frontend

```bash
cd frontend
yarn install
cd ..
```

If you need the frontend to talk to a non-default backend origin, copy
`frontend/.env.example` to `frontend/.env.local` and set
`REACT_APP_BACKEND_URL`. Leave it unset for the standard local workflow.

### 6. (Optional) Build the memvid sidecar

```bash
cd memvid_service
cargo build --release
cd ..
```

This is only required if you want to run the live memvid sidecar path. The
default backend proof commands do not require a running Rust sidecar.

To enable the Rust-backed memory path in the backend, set both
`MEMORY_BACKEND=rust` and `MEMORY_SERVICE_URL=http://localhost:3031` before
starting the FastAPI app. Startup now validates the sidecar via `/health` and
fails fast if the service is unreachable.

---

## Running the Application

### Start the backend

**Linux / macOS / WSL / Git Bash:**

```bash
./scripts/run_backend.sh
```

**Windows (PowerShell / CMD) — portable alternative:**

```powershell
python -m uvicorn backend.server:app --host 0.0.0.0 --port 8000 --reload
```

> On Windows, load `.env` first or set the relevant variables in your shell
> before running the command above. The shell script handles this automatically
> on Unix-like systems.

The script loads `.env`, validates prerequisites and mode, and starts uvicorn.
The API will be available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

### Start the frontend

```bash
cd frontend
yarn start
```

The UI will open at `http://localhost:3000`. In local development, `/api`
requests proxy to the backend at `http://localhost:8000` by default.

### (Optional) Run the memvid sidecar

```bash
./memvid_service/target/release/memvid-sidecar
```

---

## Usage

### CLI — Smoke test

Run a single end-to-end pass through the agent with a goal string:

```bash
# from repo root, with the hca package installed
hca-smoke "summarize the latest quarterly report"
```

### CLI — Evaluation

Run the full evaluation harness suite:

```bash
hca-eval all --json
```

### CLI — Replay

Replay a past run from its stored event log:

```bash
hca-replay --run-id <run-id>
```

### API

All agent operations are available via the REST API:

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/` | Backend root message |
| `POST` | `/api/status` | Create a persisted status check when Mongo is configured |
| `GET` | `/api/status` | List persisted status checks when Mongo is configured |
| `POST` | `/api/hca/run` | Create and execute a new HCA run |
| `POST` | `/api/hca/run/stream` | Stream run progress via server-sent events |
| `GET` | `/api/hca/run/{run_id}` | Fetch run state, trace, and summary |
| `POST` | `/api/hca/run/{run_id}/approve` | Grant approval for a pending action |
| `POST` | `/api/hca/run/{run_id}/deny` | Deny a pending action |
| `POST` | `/api/hca/memory/retrieve` | Retrieve memories using the `query_text` contract |
| `POST` | `/api/hca/memory/maintain` | Run memory maintenance |
| `GET` | `/api/hca/memory/list` | List stored memories |
| `DELETE` | `/api/hca/memory/{memory_id}` | Delete a memory record |

---

## Configuration

All runtime configuration lives in `hca/configs/`:

| File | Purpose |
| --- | --- |
| `base.yaml` | Workspace capacity, approval timeout, tool action classes |
| `models.yaml` | Planner and Critic model identifiers |
| `policy.yaml` | Risk level thresholds and approval requirements |
| `safety.yaml` | Proactive throttle settings |
| `memory.yaml` | Per-type retention policies |
| `environments.yaml` | Environment-specific overrides |

**Excerpt from `base.yaml`:**

```yaml
runtime:
  workspace_capacity: 7         # max items in the Global Workspace
  approval_timeout_seconds: 3600

policy:
  default_risk_threshold: low

tools:
  echo:
    action_class: low
    requires_approval: false
  store_note:
    action_class: medium
    requires_approval: true
  write_artifact:
    action_class: high
    requires_approval: true
```

### Storage path override

By default, all run artifacts are written to `<repo-root>/storage/runs/<run-id>/`. Override this with:

```bash
export HCA_STORAGE_ROOT=/data/hysight/storage
```

---

## Runtime Lifecycle

The agent moves through a deterministic state machine on every run:

```text
created → initializing → gathering_inputs → proposing → admitting
       → broadcasting → recurrent_update → action_selection
       → awaiting_approval?  → executing → observing
       → memory_commit → reporting → completed
                                            ↓
                                      (failed | halted)
```

Each transition is recorded as an event. The Critic module runs during `broadcasting` — using the LLM when available, otherwise falling back to rule-based conflict and missing-info checks.

---

## Testing

### Bootstrap

Install test dependencies before running any test commands:

```bash
python -m pip install -r backend/requirements-test.txt
```

Equivalent `make` alias: `make test-bootstrap`.

If `backend/tests/test_contract_conformance.py` or the mock sidecar tests fail
because `requests-mock` is missing, the environment was not bootstrapped with
the repo's declared test dependencies yet.

For formatter and lint tooling:

```bash
python -m pip install -r backend/requirements-dev.txt   # or: make dev-bootstrap
```

### Default proof surface (no external services required)

The fastest correct path — runs all four proof modes in order:

```bash
python scripts/run_tests.py
```

### Individual proof modes

| Proof mode | Command | CI job |
| --- | --- | --- |
| HCA pipeline proof | `pytest tests/test_hca_pipeline.py -q` | HCA Smoke Proof |
| Contract conformance proof | `pytest backend/tests/test_contract_conformance.py -q` | Contract Conformance Proof |
| Backend local proof | `pytest backend/tests/test_hca.py backend/tests/test_memory.py backend/tests/test_server_bootstrap.py -q` | Backend Local Proof |
| Backend full proof | `pytest backend/tests -q` | Backend Full Proof |

### Live sidecar proof (opt-in)

Proves real sidecar availability, retrieval, and restart semantics. Requires a
running memvid sidecar (see [Build the memvid sidecar](#6-optional-build-the-memvid-sidecar)):

```bash
RUN_MEMVID_TESTS=1 python scripts/run_tests.py --sidecar
```

Or directly:

```bash
RUN_MEMVID_TESTS=1 MEMORY_BACKEND=rust MEMORY_SERVICE_URL=http://localhost:3031 \
  pytest backend/tests/test_memvid_sidecar.py -q
```

CI job name: **Backend Live Sidecar Proof** (opt-in via `workflow_dispatch`).

### Notes

- The backend local proof validates the FastAPI app, in-process memory routes,
  and HCA runtime behavior without external services.
- The backend full proof adds mock-backed memvid boundary coverage.
- The live sidecar proof is the separate opt-in path for the real Rust sidecar.
- GitHub Actions mirrors these proof modes in `.github/workflows/backend-proof.yml`.
- The backend rejects the legacy `{"query": ...}` memory retrieve body;
  use `{"query_text": ...}` everywhere.
- CORS is disabled by default; enable with explicit absolute origins via
  `CORS_ORIGINS`.

---

## Project Conventions

- **Path resolution**: Never use `os.getcwd()` or hardcoded absolute paths. Import from `hca.paths` (`run_storage_path`, `REPO_ROOT`, etc.).
- **Approval contract**: All `high`-class tool calls must pass through `Executor.execute(..., approved=True)` with a valid `ApprovalConsumption` record.
- **Event immutability**: Storage event-log functions (`append_event`, `append_snapshot`, etc.) are append-only. Do not overwrite events.
- **Module proposals**: Cognitive modules return a `ModuleProposal`; they must not directly mutate run state.
- **LLM fallback**: Any code path that calls an LLM must degrade gracefully — catch `ImportError` and `Exception` and return a rule-based result.

---

## Contributing

1. Fork the repository and create a feature branch from `main`.
2. Write tests for any new behavior — unit tests in `hca/tests/unit/`, integration tests in `hca/tests/integration/`.
3. Run the full test suite and ensure it passes with no new failures.
4. Open a pull request with a clear description of the change and the motivation.

---

## License

[MIT](LICENSE) © Dawson Block
