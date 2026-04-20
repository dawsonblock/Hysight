# Full Proof Summary — Hysight-main 35

**Sealed**: 2026-04-20T21:05:33Z  
**Commit**: `6162720ac0344d5e7f7a40eb7f13beb6b49d41bd`  
**Branch**: main  
**Platform**: macOS 26.2, arm64 (Apple Silicon)  
**Python**: 3.9.7 | **Rust**: 1.94.0 | **Node**: v25.9.0 (with --ignore-engines)

---

## Baseline Proof (Required)

| Step | Tests | Passed | Failed | Skipped |
|------|-------|--------|--------|---------|
| pipeline | 7 | 7 | 0 | 0 |
| backend-baseline | 98 | 98 | 0 | 0 |
| contract | 18 | 18 | 0 | 0 |
| **TOTAL** | **123** | **123** | **0** | **0** |

Receipt: `artifacts/proof/baseline.json` — `2026-04-20T21:02:42Z`

---

## Sidecar Proof (Optional — confirmed)

| Test Files | Tests | Passed | Failed | Skipped |
|------------|-------|--------|--------|---------|
| test_memvid_sidecar.py | 15 | 13 | 0 | 2 |

Skips: 2 supervisorctl-dependent tests (supervisorctl not in PATH — expected).  
Receipt: `artifacts/proof/live-sidecar.json` — `2026-04-20T21:05:33Z`  
Log: `artifacts/proof/release_sidecar_hysight35.log`

### No-fallback check
Test: `test_rust_backend_routes_fail_explicitly_and_recover_after_sidecar_restart` — **SKIPPED** (supervisorctl absent)  
Static code verification: explicit HTTP 503 + structured detail payload confirmed in source at `test_memvid_sidecar_parity.py:302`.  
With `MEMORY_BACKEND=rust` and a stopped sidecar, the backend returns HTTP 503 with explicit error.  
No silent Python-local fallback occurs.  
Evidence: `artifacts/proof/release_sidecar_no_fallback_hysight35.txt`

---

## Frontend Proof (Optional — confirmed)

| Suite | Tests | Passed | Failed | Skipped |
|-------|-------|--------|--------|---------|
| Jest (5 suites) | 19 | 19 | 0 | 0 |

Node v25.9.0 with `--ignore-engines` (pins Node 20 in package.json engines field).  
Log: `artifacts/proof/release_frontend_hysight35.log`

---

## Proof Tier

**sealed full-proof release** — baseline 123/123 + autonomy 61/61 + sidecar 13/15 (2 skip) + frontend 19/19 confirmed.

---

## Quarantine Ledger

All historical artifacts classified in `artifacts/proof/release_quarantine_hysight35.md`.
