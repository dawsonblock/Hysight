# Hysight

A proof-first Hybrid Cognitive Agent runtime with bounded authority, replay-backed operations, and human approval for side effects.

[![Python](https://img.shields.io/badge/python-3.9%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)](https://react.dev/)
[![MongoDB](https://img.shields.io/badge/MongoDB-Motor%203.3-47A248?logo=mongodb&logoColor=white)](https://www.mongodb.com/)
[![Rust](https://img.shields.io/badge/Rust-Axum%200.7-CE412B?logo=rust&logoColor=white)](https://www.rust-lang.org/)
[![Verification](https://img.shields.io/badge/verification-proof--first-0f172a)](#testing)
[![Operator Surface](https://img.shields.io/badge/operator-replay--backed-0f766e)](#api)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Quick start

| I want to... | Command |
| --- | --- |
| Verify the default local proof surface | `python scripts/run_tests.py` |
| Verify the frontend operator surface | `cd frontend && yarn lint && CI=true yarn test --watch=false --runInBand && yarn build` |
| Start the backend | `./scripts/run_backend.sh` |
| Start the frontend | `cd frontend && yarn start` |
| Run the optional memvid sidecar | `cargo run --manifest-path memvid_service/Cargo.toml --release` |

If you only do one thing, run the proof surface first. Hysight treats local verification as the default entry point, not an afterthought.

```bash
# 1. Install backend test dependencies
python -m pip install -r backend/requirements-test.txt

# 2. Run the full default proof surface
python scripts/run_tests.py

# 3. Optional — live sidecar proof (requires running memvid sidecar)
RUN_MEMVID_TESTS=1 python scripts/run_tests.py --sidecar

# If localhost:3031 is already occupied, move the sidecar and proof together
MEMORY_SERVICE_PORT=3032 make run-memvid-sidecar
RUN_MEMVID_TESTS=1 MEMORY_SERVICE_PORT=3032 python scripts/run_tests.py --sidecar

# Or use the automated make wrapper around the full live sidecar proof
make run-memvid-sidecar
make proof-sidecar

# Optional — live Mongo-backed /api/status proof
make test-mongo-live
```

That is the shortest path to prove the system locally. Everything else below covers setup, configuration, operator workflows, and advanced usage.

## Jump to

- [Why Hysight](#why-hysight)
- [Architecture](#architecture)
- [Bounded Tool Catalog](#bounded-tool-catalog)
- [Running the Application](#running-the-application)
- [API](#api)
- [Testing](#testing)
- [Verification Workflow](#verification-workflow)

Hysight is built for teams who want agentic behavior without surrendering control: bounded tools, explicit approvals, replayable execution, and a default workflow that starts with proof instead of promises.

---

## Why Hysight

Hysight is an implementation of a **Hybrid Cognitive Agent (HCA)** as a bounded operator runtime. Its authority path stays inside the existing runtime, approval, executor, and replay layers instead of handing control to an open-ended autonomous loop. The cognitive modules (Planner, Critic, Perception, ToolReasoner) still compete for space in a capacity-limited **Global Workspace**, but they can only propose actions and workflow plans that the registry and executor actually implement.

The runtime executes through one canonical authority path in `hca/src/hca/runtime/runtime.py`. A run may execute either a single validated action or a bounded workflow plan that chains inspection, approval-bound mutation, verification, and deterministic reporting steps inside the same run context. Approvals, snapshots, receipts, artifacts, and replay all remain anchored to that single path, and workflow runs commonly terminate on `create_run_report` rather than the mutating step itself.

The frontend also exposes a replay-backed operator console beside the live chat surface. Recent run summaries, per-run event history, and artifact previews all come from the same bounded backend replay and storage surface rather than a second UI-only state model.

### What makes it different

- Bounded authority: proposals are cheap, but execution only happens through canonical action binding, approval policy, and the executor.
- Replay-backed operations: the operator UI and HTTP APIs read from the same stored run history, receipts, approvals, artifacts, and snapshots that the runtime writes.
- Proof-first workflow: the shortest supported path is to verify the repo locally before starting services.
- Graceful degradation: LLM-assisted modules can fall back to deterministic behavior when external model dependencies are unavailable.

### At a glance

| Layer | Role | Where to look |
| --- | --- | --- |
| Runtime | Deterministic orchestration, workflow execution, state transitions, replay | `hca/src/hca/runtime/` |
| Executor | Canonical binding, approvals, bounded tool dispatch | `hca/src/hca/executor/` |
| Workspace | Capacity-limited proposal competition and ranking | `hca/src/hca/workspace/` |
| Backend | FastAPI operator surface and memory/status endpoints | `backend/` |
| Frontend | Live chat plus replay-backed operator console | `frontend/` |
| Contracts | JSON schema and runtime/operator reference docs | `contract/`, `hca/docs/` |

---

## Architecture

### Authority path

```mermaid
flowchart LR
    Goal[Goal] --> Runtime[Runtime]
    Runtime --> Modules[Planner / Critic / Perception / ToolReasoner]
    Modules --> Workspace[Global Workspace]
    Workspace --> Scoring[Meta monitor + action scoring]
    Scoring --> Binding[Canonical action binding]
    Binding --> Approval[Approval gate]
    Approval --> Executor[Executor]
    Executor --> Tools[Bounded registry tools]
    Tools --> Storage[Events / receipts / artifacts / snapshots]
    Storage --> Replay[Replay]
    Replay --> Operator[Backend APIs + operator console]
```

### Expanded system layout

```text
┌─────────────────────────────────────────────────────────┐
│                      HCA Runtime                        │
│                                                         │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐  ┌──────┐  │
│  │ Planner  │  │  Critic  │  │Perception │  │ Tool │  │
│  │ (LLM)    │  │(LLM+Rule)│  │  (Text)   │  │Rsner │  │
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
  │  FastAPI    │            │  memvid-sidecar │
  │  Backend    │            │  (Rust / Axum)  │
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
| **Bounded Workflow Plans** | The planner/runtime can select explicit investigation and mutation-verification workflow templates that execute step-by-step without bypassing the executor, approval, or replay layers. |
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
- `summarize_search_results`
- `create_run_report`
- `create_diff_report`
- `patch_text_file`
- `replace_in_file` (legacy alias for `patch_text_file`)
- `store_note`
- `write_artifact`
- `run_command` (allowlisted only; no shell)

Mutation and reporting behavior:

- Workflow plans persist `active_workflow`, workflow checkpoints, step history, and workflow artifacts in the run context, snapshots, and replay output.
- `contract_api_drift` now performs bounded target-local evidence collection and a broader bounded contract-surface comparison before emitting a dedicated `contract_drift_summary` artifact.
- `patch_text_file` binds approval to the canonical validated action plus a file-state hash before execution.
- Successful patch actions emit before/after hashes, changed-line summaries, and a diff artifact.
- `summarize_search_results` writes a deterministic investigation artifact from bounded search output and targeted file excerpts.
- `create_diff_report` certifies an applied mutation with hashes, changed lines, diff-artifact linkage, and approval provenance.
- `create_run_report` materializes a deterministic artifact from prior events, receipts, approvals, artifacts, and memory outcomes for a run.
- In workflow runs, the terminal selected action and latest receipt may be `create_run_report`, so mutation and verification evidence should be read from workflow step history or the relevant receipt rather than assuming the last receipt is the mutating step.
- `investigate_workspace_issue` is a bounded read-only workflow tool that searches, reads targeted ranges, and emits a structured evidence artifact.
- Workflow budgets fail closed: exhausting a declared step budget emits `workflow_budget_exhausted`, and unresolved next-step arguments emit `workflow_terminated` with `next_step_unbuildable` rather than improvising execution.

Replay and memory guarantees:

- Replay and resume validate canonical action identity against approval bindings before consuming approval.
- Replay reconstructs workflow state, including active workflow metadata, workflow checkpoints, step history, and workflow artifacts.
- Local episodic memory writes are part of the normal runtime path.
- External memory-controller ingestion is best-effort, but emits `external_memory_written` or `external_memory_write_failed` events instead of failing silently.
- Command execution, when used, stays bounded to allowlisted argument arrays, repo-relative cwd, timeouts, and truncated output.

Approvals fail closed on replay:

- Resume only proceeds when the replay-backed approval record still exists and matches the pending approval for the run.
- Denied or consumed approvals halt or reject resumption instead of falling through to execution.
- Approval resume re-validates the canonical action binding before consuming approval, so tampered or stale selected-action payloads are rejected.
- Approval decisions stay authoritative in append-only approval records and replay output rather than trusting stale in-memory run context alone.

---

## Repository Structure

```text
Hysight/
├── hca/                        # Core cognitive agent package
│   ├── src/hca/
│   │   ├── api/                # Shared API models + internal compatibility app
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
- Fetch-based API client helpers

### Sidecar

- Rust (edition 2021), Axum 0.7, Tokio

### Tooling

- pytest, httpx for testing
- black, isort, flake8, mypy for code quality
- ESLint 9 and Jest via CRACO for frontend proof

---

## Prerequisites

- Python 3.9+
- Node.js 20.x and Yarn 1
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

For frontend work, switch to the repo's Node target before running Yarn
commands. The frontend package now ships `frontend/.nvmrc` and
`frontend/.node-version` pinned to Node 20 so local runs can match the CI
workflow.

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

# Optional — override the local python memory store path.
# If set, it must stay under HCA_STORAGE_ROOT.
# MEMORY_STORAGE_DIR=/path/to/custom/storage/memory

# Optional — enable the Rust memory sidecar.
# If MEMORY_BACKEND=rust is set, MEMORY_SERVICE_URL must point to a healthy
# sidecar that responds on /health or startup will fail. Leave
# MEMORY_SERVICE_URL unset in python mode; mixed mode is rejected.
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

The proof runner now sets isolated temporary `HCA_STORAGE_ROOT` and
`MEMORY_STORAGE_DIR` values for each proof step so local proof does not depend
on repo-default storage paths or leftover state.

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

The default layout is two-pane: live agent chat on the left and a persistent operator console on the right. The operator console lists recent runs, shows replay-backed workflow and approval state, and lets you inspect stored events and artifact previews without separate manual API calls.

Mongo-backed `/api/status` persistence is optional. If `MONGO_URL` and
`DB_NAME` are both unset, the backend still serves HCA and memory routes while
`/api/status` returns `503` by design.

The operator surface also exposes `GET /api/subsystems`, which always reports
the current database, memory, storage, and LLM readiness state even when
Mongo-backed status persistence is disabled.

### (Optional) Run the memvid sidecar

```bash
cargo run --manifest-path memvid_service/Cargo.toml --release
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

The deployed HTTP surface is `backend.server:app`. The `hca/src/hca/api/app.py`
application is a repo-local compatibility layer for direct runtime tests and
inspection, not the frontend or container entrypoint.

All agent operations are available via the REST API:

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/` | Backend root message |
| `POST` | `/api/status` | Create a persisted status check when Mongo is configured |
| `GET` | `/api/status` | List persisted status checks when Mongo is configured |
| `GET` | `/api/subsystems` | Report database, memory, storage, and LLM subsystem health |
| `POST` | `/api/hca/run` | Create and execute a new HCA run |
| `POST` | `/api/hca/run/stream` | Stream run progress via server-sent events |
| `GET` | `/api/hca/runs` | List recent replay-backed run summaries |
| `GET` | `/api/hca/run/{run_id}` | Fetch run state, trace, and summary |
| `GET` | `/api/hca/run/{run_id}/events` | List bounded newest-first run events |
| `GET` | `/api/hca/run/{run_id}/artifacts` | List stored artifact records for a run |
| `GET` | `/api/hca/run/{run_id}/artifacts/{artifact_id}` | Fetch a bounded artifact content preview |
| `POST` | `/api/hca/run/{run_id}/approve` | Grant approval for a pending action |
| `POST` | `/api/hca/run/{run_id}/deny` | Deny a pending action |
| `POST` | `/api/hca/memory/retrieve` | Retrieve memories using the `query_text` contract |
| `POST` | `/api/hca/memory/maintain` | Run memory maintenance |
| `GET` | `/api/hca/memory/list` | List stored memories |
| `DELETE` | `/api/hca/memory/{memory_id}` | Delete a memory record |

### Operator API examples

The frontend operator console uses the same bounded replay-backed HTTP surface
shown below. There is no separate UI-only state model.

```bash
# List recent runs
curl "http://localhost:8000/api/hca/runs?limit=5"

# Inspect backend subsystem readiness and degraded-mode state
curl "http://localhost:8000/api/subsystems"

# Fetch the newest events for a specific run
curl "http://localhost:8000/api/hca/run/<run-id>/events?limit=20"

# List stored artifacts for a run
curl "http://localhost:8000/api/hca/run/<run-id>/artifacts?limit=20"

# Preview a single artifact body
curl "http://localhost:8000/api/hca/run/<run-id>/artifacts/<artifact-id>"
```

### Runtime reference docs

- [hca/docs/operator-runtime-contract.md](hca/docs/operator-runtime-contract.md)
  freezes the current bounded operator/runtime contract from code reality.
- [hca/docs/runtime-contracts.md](hca/docs/runtime-contracts.md)
  describes the runtime types, workflow semantics, and state-machine
  guarantees.
- [contract/schema.json](contract/schema.json) is the authoritative HTTP
  payload contract used by the backend contract-conformance proof.

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
./scripts/proof_local.sh
```

Equivalent direct invocation:

```bash
python scripts/run_tests.py
```

This backend proof path is the authoritative local runtime proof. It does not
claim frontend verification or live Rust sidecar coverage by itself.

### Individual proof modes

| Proof mode | Command | CI job |
| --- | --- | --- |
| HCA pipeline proof | `pytest tests/test_hca_pipeline.py -q` | HCA Smoke Proof |
| Contract conformance proof | `pytest backend/tests/test_contract_conformance.py -q` | Contract Conformance Proof |
| Backend local proof | `pytest backend/tests/test_hca.py backend/tests/test_memory.py backend/tests/test_server_bootstrap.py -q` | Backend Local Proof |
| Backend full proof | `pytest backend/tests -q` | Backend Full Proof |

### Frontend proof

The operator UI is under its own CI proof surface in
`.github/workflows/frontend-proof.yml`.

Run it locally with:

```bash
cd frontend
yarn install --frozen-lockfile
yarn lint
CI=true yarn test --watch=false --runInBand
yarn build
```

This verifies the actual frontend toolchain in use today: dependency install,
ESLint, Jest, API client boundary tests, and the production build.

## Verification Workflow

Hysight also ships repo-scoped VS Code customizations for verification and
release-summary work. They are intended to keep proof runs narrow, keep
`test_result.md` up to date, and make the next verifier explicit instead of
reconstructing context from chat history.

### Shared handoff file

- `test_result.md` is the coordination file for implementation and verification
  passes.
- The protocol block at the top of that file is authoritative and should be
  preserved exactly.
- Backend and frontend verifiers record proof evidence, retest needs, and
  handoff notes there.

### Repo-scoped custom agents

- [`.github/agents/backend-verification.agent.md`](.github/agents/backend-verification.agent.md)
  validates FastAPI, backend runtime, Mongo-backed status proof, and sidecar
  proof work.
- [`.github/agents/frontend-verification.agent.md`](.github/agents/frontend-verification.agent.md)
  validates React regressions, API-client boundary tests, lint, Jest, and the
  production build.
- [`.github/agents/release-notes.agent.md`](.github/agents/release-notes.agent.md)
  turns [HARDENING_REPORT.md](HARDENING_REPORT.md),
  [REPAIR_REPORT.md](REPAIR_REPORT.md), and
  [RELEASE_NOTES.md](RELEASE_NOTES.md) into concise release-facing summaries.

### Recommended handoff flow

1. Run the prompt in
   [`.github/prompts/prepare-verification-handoff.prompt.md`](.github/prompts/prepare-verification-handoff.prompt.md)
   to update `test_result.md` before delegating verification.
2. Invoke the backend or frontend verification agent based on the files and
   proof surface involved.
3. Use the release-notes agent when the implementation or repair reports need
   to be collapsed into release-facing documentation.

The handoff prompt prepares the tracking file and recommends the next verifier;
it does not run tests by itself.

### Live sidecar proof (opt-in locally)

Proves real sidecar availability, retrieval, and restart semantics. Requires a
running memvid sidecar (see [Build the memvid sidecar](#6-optional-build-the-memvid-sidecar)):

```bash
RUN_MEMVID_TESTS=1 python scripts/run_tests.py --sidecar

# If localhost:3031 is busy on macOS or another local service is using it
MEMORY_SERVICE_PORT=3032 make run-memvid-sidecar
RUN_MEMVID_TESTS=1 MEMORY_SERVICE_PORT=3032 python scripts/run_tests.py --sidecar

# Or use the explicit make wrapper around the same proof command
make run-memvid-sidecar
make proof-sidecar
```

Or directly:

```bash
RUN_MEMVID_TESTS=1 MEMORY_BACKEND=rust MEMORY_SERVICE_URL=http://localhost:3032 \
  pytest backend/tests/test_memvid_sidecar.py -q
```

The proof runner defaults to `http://localhost:3031`, but it will derive the
loopback URL from `MEMORY_SERVICE_PORT` when `MEMORY_SERVICE_URL` is unset.

### Live Mongo-backed `/api/status` proof (opt-in locally)

Proves the real Mongo-backed status persistence path against a live MongoDB
instance without changing the default service-free proof surface:

```bash
make test-mongo-live

# Override the live Mongo connection when needed
LIVE_MONGO_URL=mongodb://127.0.0.1:27017 \
LIVE_MONGO_DB_NAME=hysight_live \
make test-mongo-live
```

CI job name: **Backend Live Sidecar Proof**. Push and pull request runs execute
this supported sidecar mode in CI; `workflow_dispatch` exposes an input so
manual runs can skip or include it explicitly.

### Notes

- The backend local proof validates the FastAPI app, in-process memory routes,
  and HCA runtime behavior without external services.
- The backend full proof adds mock-backed memvid boundary coverage.
- The live sidecar proof remains a separate local opt-in path for the real Rust
  sidecar, even though CI also exercises that supported mode.
- `./scripts/proof_local.sh` is the no-logic wrapper around the canonical
  proof authority `python scripts/run_tests.py`.
- GitHub Actions mirrors the backend proof modes in `.github/workflows/backend-proof.yml`
  and the frontend proof surface in `.github/workflows/frontend-proof.yml`.
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
