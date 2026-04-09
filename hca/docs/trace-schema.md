## Trace schema

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
