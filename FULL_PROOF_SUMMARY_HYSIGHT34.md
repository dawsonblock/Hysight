# Full Proof Summary — Hysight-main 34

**Sealed**: 2026-04-20T20:05:31Z  
**Commit**: `5d68ab48030e67571015c60316683dc9a772a0d4`  
**Branch**: main  
**Platform**: macOS 26.2, arm64 (Apple Silicon)  
**Python**: 3.9.7 | **Rust**: 1.94.0 | **Node**: v25.9.0 (frontend skipped — Node 20 required)

---

## Baseline Proof (Required)

| Step | Tests | Passed | Failed | Skipped |
|------|-------|--------|--------|---------|
| pipeline | 7 | 7 | 0 | 0 |
| backend-baseline | 98 | 98 | 0 | 0 |
| contract | 18 | 18 | 0 | 0 |
| **TOTAL** | **123** | **123** | **0** | **0** |

Receipt: `artifacts/proof/baseline.json` — `2026-04-20T20:06:17Z`

---

## Sidecar Proof (Optional — confirmed)

| Test Files | Tests | Passed | Failed | Skipped |
|------------|-------|--------|--------|---------|
| test_memvid_sidecar.py + test_memvid_sidecar_parity.py | 19 | 17 | 0 | 2 |

Skips: 2 supervisorctl-dependent tests (supervisorctl not in PATH — expected).  
Receipt: `artifacts/proof/live-sidecar.json` — `2026-04-20T20:13:42Z`  
Log: `artifacts/proof/release_sidecar_hysight34.log`

### No-fallback check
Test: `test_rust_backend_routes_fail_explicitly_and_recover_after_sidecar_restart` — **PASSED**  
With `MEMORY_BACKEND=rust` and a stopped sidecar, the backend returns HTTP 503 with explicit error.  
No silent Python-local fallback occurs.  
Evidence: `artifacts/proof/release_sidecar_no_fallback_hysight34.txt`

---

## Frontend Proof (Optional — skipped)

Reason: Frontend requires Node 20.x; system Node is v25.9.0.  
No frontend source changes were made in hysight-main 34 (this revision changed only backend autonomy routes and tests).  
Last known passing frontend proof: `artifacts/proof/frontend.json` (2026-04-19).  
Log: `artifacts/proof/release_frontend_hysight34.log`

---

## Proof Tier

**sealed local-core release** — baseline 123/123 + sidecar 17/19 (2 skip) confirmed.  
Frontend optional step skipped due to toolchain constraint.

---

## Quarantine Ledger

All historical artifacts classified in `artifacts/proof/release_quarantine_hysight34.md`.
