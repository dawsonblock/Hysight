# Sidecar Parity Report

## Supported startup path

- The supported direct sidecar start path is `make run-memvid-sidecar`, which resolves to `cargo run --manifest-path memvid_service/Cargo.toml --release` with `MEMORY_SERVICE_PORT`.
- The supported full proof harness is `./.venv/bin/python scripts/proof_sidecar.py`, usually reached through `make proof-sidecar`.
- The sidecar persists under `MEMORY_DATA_DIR`. The official proof harness creates an isolated temporary data root per run.

## Proven

- Fresh official live-sidecar receipt: `MEMORY_SERVICE_PORT=3032 ./.venv/bin/python scripts/proof_sidecar.py` passed on 2026-04-18 and refreshed `artifacts/proof/live-sidecar.json` plus `artifacts/proof/history/live-sidecar-20260418T211556Z.json`.
- Official live-sidecar receipt result: 13 passed, 2 skipped. The skipped cases are the supervisor-controlled restart tests.
- New live parity audit slice: `./.venv/bin/python -m pytest backend/tests/test_memvid_sidecar_parity.py -q --run-live` passed with 4 tests.
- Proven by the new parity tests:
  - `ingest`, `retrieve`, `list`, `delete`, and `maintain` match the local python controller at the contract level for supported fields and counts.
  - Missing delete parity now matches the local controller. Rust-backed delete of a nonexistent memory returns `False`, and the backend route returns `404 Memory not found` instead of a sidecar failure `503`.
  - Graceful process restart with the same `MEMORY_DATA_DIR` preserves ingested records and preserves deletes.
  - Repeated backend requests during sidecar outage fail explicitly with `503` and recover once the sidecar comes back.
- No silent fallback from `MEMORY_BACKEND=rust` to local memory was observed. Rust mode stays fail-closed at startup and during request handling.

## Findings

- Resolved defect: rust-backed delete treated a sidecar `404` as a transport failure. That broke parity with local mode and turned backend delete of a missing memory into `503`. The fix is in `memory_service/controller.py`.
- Official proof coverage is still narrower than the audit coverage. `backend/tests/test_memvid_sidecar.py` skips restart persistence unless `supervisorctl` is present, so the official receipt still does not prove restart parity.
- The new parity tests prove graceful restart persistence without changing the official proof runner.

## Works locally but not fully proven

- Maintain/report parity is proven for fresh records and non-expiry cases.
- Outage/recovery semantics are proven for repeated backend list requests, not for every backend memory operation under simultaneous outage.
- Graceful restart persistence is proven. Crash durability is not.

## Unproven

- Expiry persistence across sidecar restart remains unproven. The audit did not produce an expired live sidecar record, so restart behavior for expired state is still not runtime-proven.
- The official sidecar receipt does not yet include the new graceful restart parity tests.

## Blockers

- Remaining hard blocker: none after the missing-delete parity fix.
- Remaining proof gap: the official live-sidecar receipt still skips restart persistence and does not cover expiry persistence.

## Commands and evidence

```bash
MEMORY_SERVICE_PORT=3032 ./.venv/bin/python scripts/proof_sidecar.py
./.venv/bin/python -m pytest backend/tests/test_memvid_sidecar_parity.py -q --run-live
```

- Receipt: `artifacts/proof/live-sidecar.json`
- History receipt: `artifacts/proof/history/live-sidecar-20260418T211556Z.json`
- JUnit: `test_reports/pytest/backend-live-sidecar-proof.xml`