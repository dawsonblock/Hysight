## Evaluation Harnesses

The v5 evaluation layer is a deterministic harness suite rather than a benchmark runner. Each harness executes a small scenario and returns structured case results plus harness-specific metrics.

### Coordination

The coordination harness runs a greeting case and an approval-gated note-storage case. It checks:

- selected action accuracy
- completion rate
- approval resume rate for write-side effects
- whether module proposals and recurrent passes were emitted

### Metacognition

The metacognition harness feeds the monitor four explicit scenarios:

- clean workspace
- contradictory memory retrieval
- missing required tool arguments
- unsupported tool request

It reports per-case outcomes and an overall accuracy score.

### Memory

The memory harness verifies three concrete behaviors:

- retrieval returns the expected record payload
- contradiction marking survives conflicting writes on the same subject
- bounded freshness filtering works through `max_staleness`

### Proactivity

The proactivity harness checks that proactive write actions are gated behind `require_approval`, while benign proactive echo actions are allowed to proceed.

### Embodiment

The embodiment harness runs an approval-gated `write_artifact` scenario and verifies that:

- the selected action is `write_artifact`
- an artifact record is emitted
- the artifact file exists on disk

### Audit

The audit harness executes an approval-gated note write, reconstructs the run from events, loads the latest valid snapshot, and checks:

- replay state matches persisted run state
- replay state matches the latest snapshot
- selected action is recoverable
- replay discrepancies are empty
- episodic memory was written

## CLI Usage

Run a single harness:

```bash
hca-eval coordination
```

Run all harnesses with structured output:

```bash
hca-eval all --json
```

The CLI returns harness metrics plus per-case details. It is intended for regression checks and contract validation, not statistical model evaluation.
