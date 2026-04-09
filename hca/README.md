# Hybrid Cognitive Agent

This project implements a small, bounded cognitive agent runtime.  It is inspired by ideas from global workspace and predictive processing research but stays firmly in the domain of software engineering.  It does **not** claim that the agent is conscious.  Instead, the runtime focuses on better task coordination, long‑term persistence, self‑monitoring and explicit control of side effects.

## Key features

* **State machine** – every run follows a strict sequence of states; illegal transitions are rejected.  This makes runs easy to reason about and replay.
* **Global workspace** – a small, capacity‑limited store where competing module proposals are admitted, ranked and broadcast back.  Capacity pressure forces the agent to prioritise.
* **Meta monitor** – a component that inspects the workspace for contradictions, missing information and other red flags and emits simple control signals such as `proceed` or `ask_user`.
* **Typed memory stores** – episodic, semantic, procedural and identity records are stored separately with provenance.  Memory writes are durable and retrieval exposes confidence and staleness metadata.
* **Execution authority** – all external side effects are performed through a single executor which enforces policy and approval requirements.  High‑risk actions require explicit approval.
* **Logging and replay** – every significant event is appended to a JSONL log.  Runs can be reconstructed from this log and associated artifacts.
* **API and CLI** – a minimal FastAPI application exposes endpoints to create runs, inspect state and grant approvals.  CLI entry points provide smoke, evaluation and replay commands.

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

This codebase is a minimal MVP intended as a foundation for further work.  It does **not** include real language models, complex planners or social reasoning.  The modules provided are deterministic stubs.  The runtime currently persists data to the local filesystem only and does not implement robust recovery after process failure.  It is therefore unsuitable for production use without further hardening.
