# Hysight-41 Optional Proof Summary

**Release tag:** hysight-41
**Base commit:** `00ac024248272485bcf687635d7c7b1f97f567db`
**Sealed at:** 2026-04-21T05:29:12Z

---

## 1. Executive Verdict

All optional proof surfaces requested for hysight-41 were freshly exercised on this
workspace revision. The live Rust sidecar receipt passed, additive parity tests passed,
the stopped-sidecar backend check failed closed, and the frontend proof passed on the
exact enforced Node/Yarn runtime.

## 2. Machine Facts

- Platform: macOS 26.2, arm64
- Python: 3.9.7
- Rust: `rustc 1.94.0`, `cargo 1.94.0`
- Node: `v24.15.0`
- Yarn: `1.22.22`

## 3. Sidecar Result

| Metric | Value |
|--------|-------|
| Receipt outcome | ✅ PASS |
| Receipt passed | 13 |
| Receipt skipped | 2 |
| Receipt failed | 0 |
| Receipt | `artifacts/proof/live-sidecar.json` |
| Canonical command | `./.venv/bin/python scripts/proof_sidecar.py` |
| Service port | `53104` |

Additive parity evidence:

| Metric | Value |
|--------|-------|
| Parity outcome | ✅ PASS |
| Parity passed | 4 |
| Parity failed | 0 |
| Command | `./.venv/bin/python -m pytest backend/tests/test_memvid_sidecar_parity.py --run-live` |
| Log | `artifacts/proof/release_sidecar_hysight41.log` |

## 4. No-Fallback Result

The backend was started with `MEMORY_BACKEND=rust` and `MEMORY_SERVICE_URL` pointed at
the now-stopped sidecar on `http://127.0.0.1:53584`. Startup failed immediately on the
health probe rather than silently reverting to python-local memory.

- Evidence: `artifacts/proof/release_sidecar_no_fallback_hysight41.txt`
- Exit marker: `NO_FALLBACK_EXIT=1`
- Result: ✅ PASS (explicit fail-closed behavior)

## 5. Frontend Result

| Metric | Value |
|--------|-------|
| Outcome | ✅ PASS |
| Passed | 20 |
| Failed | 0 |
| Receipt | `artifacts/proof/frontend.json` |
| Runtime | Node `24.15.0`, Yarn `1.22.22` |
| Covered stages | runtime-verification, fixture-drift, lint, jest, build |
| Log | `artifacts/proof/release_frontend_hysight41.log` |

## 6. Historical Optional Receipts Ignored

All older optional summaries, older `live-sidecar` history receipts, and the historical
`frontend.json` / `live-sidecar.json` contents that predated this seal are non-authoritative
for hysight-41. The full quarantine list lives in
`artifacts/proof/release_quarantine_hysight41.md`.

## 7. Optional-Surface Classification

**All requested optional proof surfaces are freshly proven for hysight-41.**

That includes:

- canonical live sidecar receipt
- additive live sidecar parity
- explicit stopped-sidecar fail-closed behavior
- exact-runtime frontend proof