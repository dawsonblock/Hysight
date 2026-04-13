# Trace schema

The runtime writes an append‑only log of events in JSON Lines format (`events.jsonl`).  Each event record contains:

* `event_id`: a unique identifier for the event.
* `run_id`: the run the event belongs to.
* `timestamp`: an ISO 8601 timestamp.
* `event_type`: a string from the `EventType` enum.
* `actor`: the component that emitted the event (e.g. `runtime`, `executor`, `module.planner`).
* `payload`: a serialisable dictionary with event‑specific data.
* `provenance`: references to preceding events or memory records that influenced this event.
* `prior_state`: the runtime state before the event occurred.
* `next_state`: the runtime state after the event, if the event triggers a state transition.

Additional append‑only logs include:

* `receipts.jsonl` – execution receipts for actions performed by the executor.
* `approvals.jsonl` – requests for approval and decisions.
* `artifacts.jsonl` – records of files or other artefacts produced by actions.
* `snapshots.jsonl` – periodic serialisations of runtime state and workspace summaries.

These logs, along with `run.json` (run metadata) and memory stores, allow complete reconstruction of a run.

The append-only logs are the raw trace truth, but they are not the primary operator summary contract. The canonical normalized replay surface is `GET /api/hca/run/{run_id}` and `GET /api/hca/runs`, defined by `hca/src/hca/api/models.py` and populated by `hca/src/hca/api/run_views.py`.

Planner fallback state, perception fallback state, critic verdict scores, and workflow terminal outcome may originate in raw event payloads, but operator-facing consumers should use the normalized summary fields instead of scraping those values back out of the raw trace. The `/events` endpoint remains the correct boundary for full forensic payload inspection.
