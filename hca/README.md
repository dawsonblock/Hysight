# Hybrid Cognitive Agent

This project implements a small, bounded cognitive agent runtime.  It is inspired by ideas from global workspace and predictive processing research but stays firmly in the domain of software engineering.  It does **not** claim that the agent is conscious.  Instead, the runtime focuses on better task coordination, long‑term persistence, self‑monitoring and explicit control of side effects.

## Key features

* **State machine** – every run follows a strict sequence of states; illegal transitions are rejected.  This makes runs easy to reason about and replay.
* **Global workspace** – a small, capacity‑limited store where competing module proposals are admitted, ranked and broadcast back.  Capacity pressure forces the agent to prioritise.
* **Meta monitor** – a component that inspects the workspace for contradictions, missing information and other red flags and emits simple control signals such as `proceed` or `ask_user`.
* **Optional LLM integrations** – Planner, Critic and TextPerception can call external LLM providers when configured, but each path degrades to deterministic fallback logic when the integration is unavailable.
* **Typed memory stores** – episodic, semantic, procedural and identity records are stored separately with provenance.  Local episodic writes are authoritative; external memory-controller ingestion is best-effort but now emits explicit success or failure events.
* **Execution authority** – all external side effects are performed through a single executor which enforces registry-defined validation, policy, approval, and artifact handling.  Mutating tools require explicit approval and resume with the same canonical action binding.
* **Bounded workflow plans** – the runtime can select explicit workflow templates for investigation and mutation-with-verification tasks.  Those workflows run step-by-step through the same executor, approval, snapshot, and replay path instead of introducing a separate autonomous loop.
* **Logging and replay** – every significant event is appended to a JSONL log.  Runs can be reconstructed from this log and associated artifacts, and approval-bound resume validates the same canonical action identity before execution.
* **API and CLI** – a minimal FastAPI application exposes endpoints to create runs, inspect state and grant approvals.  CLI entry points provide smoke, evaluation and replay commands.

## Bounded tool surface

The package is intentionally small and bounded.  The current registry covers repo inspection (`list_dir`, `stat_path`, `glob_workspace`, `search_workspace`, `read_text_range`), evidence/report generation (`investigate_workspace_issue`, `summarize_search_results`, `create_run_report`, `create_diff_report`, `write_artifact`), approval-bound mutation (`patch_text_file`), memory/note persistence (`store_note`), and one allowlisted command path (`run_command`).

## Running the project

Install in editable mode and run the smoke test:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
hca-smoke
```

This will create a new run, execute a simple tool call through the executor, commit the result to memory and print the final state.  You can then replay the run with `hca-replay <run_id>`.

For deterministic regression coverage, run the built-in evaluation harnesses:

```bash
hca-eval all --json
pytest
```

The evaluation CLI exercises coordination, metacognition, memory, proactivity, embodiment and replay/audit behaviors and returns structured metrics for each harness.

## Limitations

This codebase is still a bounded runtime intended as a foundation for further work.  Several modules support optional external LLM integrations, but those paths only activate when the relevant dependencies and credentials are configured.  The runtime now supports bounded multi-step workflow chains, but those chains are template-driven and registry-backed rather than open-ended autonomy.  Workflow runs often end on a generated run-report receipt, so downstream consumers must inspect workflow step history when they need the mutating or verification receipt specifically.  Persistence is still primarily local-filesystem based unless you pair the package with the surrounding backend and memory sidecar.  The package therefore remains unsuitable as a standalone production deployment without additional operational hardening.
