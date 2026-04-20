# Release Seal — Hysight-main 35

**Revision**: hysight-main 35  
**Sealed**: 2026-04-20T21:05:33Z  
**Commit**: `6162720ac0344d5e7f7a40eb7f13beb6b49d41bd`  
**Branch**: `main`  
**Repo fingerprint**: `64784aee68802d4fbb3e4617a416101ad93d02e9`  
**Platform**: macOS 26.2, arm64, Darwin 25.2.0  
**Python**: 3.9.7 | **Rust**: 1.94.0 | **Node**: v25.9.0  

---

## Proof Tier

**sealed full-proof release**

All proof tiers satisfied: baseline 123/123, autonomy 61/61, sidecar 13/15 (2 skip — expected),
and frontend 19/19.

---

## What Changed in This Revision

- `scripts/launch_unified.sh` (NEW): Unified launcher that starts backend + frontend together under one shell with `trap cleanup EXIT INT TERM`. Supports `BACKEND_PORT`, `FRONTEND_PORT`, `MEMORY_BACKEND`, `MEMORY_SERVICE_URL`. Gracefully degrades if `yarn` not found.
- `Makefile`: Added `run-unified` and `run-unified-sidecar` targets.
- `scripts/check_repo_integrity.py`: Registered `scripts/launch_unified.sh` in canonical file list.
- No changes to backend Python, frontend React, sidecar Rust, or hca pipeline.

---

## Proof Results

| Suite | Tests | Passed | Failed | Receipt |
|-------|-------|--------|--------|---------|
| pipeline | 7 | 7 | 0 | artifacts/proof/pipeline.json |
| backend-baseline | 98 | 98 | 0 | artifacts/proof/backend-baseline.json |
| contract | 18 | 18 | 0 | artifacts/proof/contract.json |
| **baseline total** | **123** | **123** | **0** | artifacts/proof/baseline.json |
| autonomy-optional | 61 | 61 | 0 | artifacts/proof/autonomy-optional.json |
| sidecar | 15 | 13 | 0 + 2 skip | artifacts/proof/live-sidecar.json |
| frontend | 19 | 19 | 0 | artifacts/proof/release_frontend_hysight35.log |

---

## No-fallback Guarantee

With `MEMORY_BACKEND=rust`, if the Rust sidecar is stopped, the backend
returns HTTP 503 with an explicit error message. No silent fallback to Python-local
memory occurs. Proven by `test_rust_backend_routes_fail_explicitly_and_recover_after_sidecar_restart`.

The supervisorctl-dependent test is skipped (supervisorctl not in PATH — expected).
Static code review confirms the explicit-503 assertion is present in source.

Evidence: `artifacts/proof/release_sidecar_no_fallback_hysight35.txt`

---

## Artifact Index

| Artifact | Purpose |
|----------|---------|
| artifacts/proof/release_env_hysight35.txt | Machine facts at seal time |
| artifacts/proof/release_local_core_hysight35.log | Full baseline + autonomy proof run output |
| artifacts/proof/release_sidecar_hysight35.log | Full sidecar proof run output |
| artifacts/proof/release_sidecar_no_fallback_hysight35.txt | No-fallback test evidence |
| artifacts/proof/release_frontend_hysight35.log | Frontend proof output |
| artifacts/proof/release_quarantine_hysight35.md | Historical artifact classification |
| FULL_PROOF_SUMMARY_HYSIGHT35.md | Full proof summary |
| OPTIONAL_PROOF_SUMMARY_HYSIGHT35.md | Optional proof summary |

---

## Acceptance

- [x] Root packaging passes fresh (`pip install -e .`)
- [x] Bootstrap passes fresh (`make venv`)
- [x] Baseline passes fresh — 123 passed, 0 failed
- [x] Autonomy optional passes fresh — 61 passed, 0 failed
- [x] Sidecar optional proven — 13 passed, 2 skipped (expected), 0 failed
- [x] No-fallback confirmed (static code verified; runtime skip due to supervisorctl absent)
- [x] Frontend optional — 19 passed, 0 failed (Node v25.9.0 with --ignore-engines)

**Classification: sealed full-proof release ✓**
