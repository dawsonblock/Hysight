# Release Seal — Hysight-main 34

**Revision**: hysight-main 34  
**Sealed**: 2026-04-20T20:05:31Z  
**Commit**: `5d68ab48030e67571015c60316683dc9a772a0d4`  
**Branch**: `main`  
**Repo fingerprint**: `9a3fcd167765afdd38072291d66cc27ee6f4b047`  
**Platform**: macOS 26.2, arm64, Darwin 25.2.0  
**Python**: 3.9.7 | **Rust**: 1.94.0 | **Node**: v25.9.0  

---

## Proof Tier

**sealed local-core release**

Minimum acceptance criteria satisfied (baseline 123/123). Sidecar optional proof also confirmed.  
Frontend optional proof skipped (Node version mismatch — no frontend source changes in rev 34).

---

## What Changed in This Revision

- `backend/server_autonomy_routes.py`: Fixed `_status_to_response()` to project `last_checkpoint` through `_checkpoint_to_response()` helper — checkpoint is now included in all autonomy status responses.
- `scripts/run_tests.py`: Added 3 new autonomy test files to the `AUTONOMY_OPTIONAL_STEP` definition.
- No changes to frontend, sidecar, memory service, or hca pipeline.

---

## Proof Results

| Suite | Tests | Passed | Failed | Receipt |
|-------|-------|--------|--------|---------|
| pipeline | 7 | 7 | 0 | artifacts/proof/pipeline.json |
| backend-baseline | 98 | 98 | 0 | artifacts/proof/backend-baseline.json |
| contract | 18 | 18 | 0 | artifacts/proof/contract.json |
| **baseline total** | **123** | **123** | **0** | artifacts/proof/baseline.json |
| autonomy-optional | 61 | 61 | 0 | artifacts/proof/autonomy-optional.json |
| sidecar | 19 | 17 | 0 + 2 skip | artifacts/proof/live-sidecar.json |
| frontend | — | skipped | — | artifacts/proof/release_frontend_hysight34.log |

---

## No-fallback Guarantee

With `MEMORY_BACKEND=rust`, if the Rust sidecar is stopped, the backend
returns HTTP 503 with an explicit error message. No silent fallback to Python-local
memory occurs. Proven by `test_rust_backend_routes_fail_explicitly_and_recover_after_sidecar_restart`.

Evidence: `artifacts/proof/release_sidecar_no_fallback_hysight34.txt`

---

## Artifact Index

| Artifact | Purpose |
|----------|---------|
| artifacts/proof/release_env_hysight34.txt | Machine facts at seal time |
| artifacts/proof/release_local_core_hysight34.log | Full baseline + autonomy proof run output |
| artifacts/proof/release_sidecar_hysight34.log | Full sidecar proof run output |
| artifacts/proof/release_sidecar_no_fallback_hysight34.txt | No-fallback test evidence |
| artifacts/proof/release_frontend_hysight34.log | Frontend skip documentation |
| artifacts/proof/release_quarantine_hysight34.md | Historical artifact classification |
| FULL_PROOF_SUMMARY_HYSIGHT34.md | Full proof summary |
| OPTIONAL_PROOF_SUMMARY_HYSIGHT34.md | Optional proof summary |

---

## Acceptance

- [x] Root packaging passes fresh (`pip install -e .`)
- [x] Bootstrap passes fresh (`make venv`)
- [x] Baseline passes fresh — 123 passed, 0 failed
- [x] Autonomy optional passes fresh — 61 passed, 0 failed
- [x] Sidecar optional proven — 17 passed, 2 skipped (expected), 0 failed
- [x] No-fallback confirmed
- [ ] Frontend optional — **skipped** (Node 20 not available; no frontend changes in rev 34)

**Classification: sealed local-core release ✓**

---

## Quarantine

All historical proof artifacts (revisions 27–32) classified in  
`artifacts/proof/release_quarantine_hysight34.md`. They are retained as read-only
historical record. Only the fresh artifacts listed above are authoritative for rev 34.
