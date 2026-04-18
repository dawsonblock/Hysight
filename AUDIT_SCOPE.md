# Audit Scope

## Proven by current receipts

- Running `./.venv/bin/python scripts/run_tests.py` on 2026-04-18 refreshed `artifacts/proof/baseline.json` and passed the declared local baseline.
- The current baseline receipt proves the supported service-free authority path only:
  - HCA pipeline proof: 7 passed.
  - Backend baseline proof: 96 passed.
  - Contract conformance proof: 18 passed.
- That proves the local python-backed memory mode, the repo-local backend runtime surface exercised by `scripts/run_tests.py`, and contract-shape conformance for the declared backend endpoints.
- The baseline receipt is honest about scope. It explicitly omits `frontend`, `integration`, `mongo-live`, and `sidecar`.

## Not proven by current receipts

- A real reachable rust sidecar started through the supported `memvid_service/` path.
- Sidecar parity versus the local python memory authority for live ingest, retrieve, list, delete, maintain, and outage handling.
- Graceful restart persistence or outage/recovery behavior for the sidecar-backed mode.
- Frontend proof on the declared supported toolchain for the current snapshot.
- Clean-start bootstrap and release reproducibility from the published docs and Make targets.
- Bounded concurrency and stress behavior for backend runs, local memory state, and SSE streams.
- Multi-client fan-out for the same existing SSE run stream.