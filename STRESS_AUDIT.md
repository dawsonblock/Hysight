# Stress Audit

## Boundaries used

- The audit intentionally used a small bounded stress layer instead of a broad load framework.
- Local stress slice command:

```bash
./.venv/bin/python -m pytest backend/tests/test_stress_audit.py -q --run-integration
```

- Sidecar outage/recovery stress slice command:

```bash
./.venv/bin/python -m pytest backend/tests/test_memvid_sidecar_parity.py -q --run-live
```

## Proven

- `backend/tests/test_stress_audit.py` passed with 4 tests.
- `backend/tests/test_memvid_sidecar_parity.py` passed with 4 tests.
- Proven by those bounded stress slices:
  - Multiple backend runs can be created in parallel without cross-run event contamination.
  - The local memory controller tolerated concurrent ingest, delete, maintain, and list activity, then reloaded cleanly from disk with no corrupted JSONL state.
  - Multiple SSE run streams can execute in parallel with monotonic per-stream step ordering.
  - Repeated connect/disconnect cycles close cleanly with final `done` events.
  - Repeated backend requests during sidecar outage fail explicitly with `503` and recover after the sidecar restarts.
- No deadlocks or hangs were reproduced in the bounded audit.

## Findings by severity

### Critical

- None reproduced.

### Serious

- None reproduced.

### Tolerable

- The official proof runner does not cover these bounded stress slices. They exist as audit tests only.
- SSE stress coverage is limited to parallel independent streams and repeated reconnects. It does not prove fan-out from one existing run stream to many listeners.

### Unproven but suspicious

- Same-run multi-client SSE fan-out remains unproven because the current API surface exposes `POST /api/hca/run/stream` to create a new streaming run, not to attach multiple listeners to one existing run.
- Rust sidecar expiry persistence across restart remains unproven and should be treated as suspicious until a live test can prove it.

## Blocker-ranked summary

- Critical blockers: none reproduced.
- Serious blockers: none reproduced.
- Tolerable gaps: official proof surface still stops short of these stress slices.
- Suspicious but unproven gaps: same-run SSE fan-out and sidecar expiry persistence across restart.