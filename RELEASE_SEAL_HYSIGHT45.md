# Hysight-45 Release Seal

**Release tag:** hysight-45
**Commit:** `189980254f92214198fff7d561ca0405c7ccce82`
**Sealed at:** 2026-04-21T23:03:15Z
**Classification:** **sealed local-core release**

---

## Proof Counts

| Suite | Passed | Failed |
|-------|--------|--------|
| Baseline (pipeline + backend + contract) | 123 | 0 |
| Autonomy | 66 | 0 |
| Frontend | 67 | 0 |
| **Total (local-core)** | **256** | **0** |

Sidecar: **CARRY-FORWARD** — last proved at hysight-42 (13/0).

---

## Evidence Files

All proof ran against the live repo at the exact commit listed above.

- `artifacts/proof/pipeline.json`
- `artifacts/proof/backend-baseline.json`
- `artifacts/proof/contract.json`
- `artifacts/proof/baseline.json`
- `artifacts/proof/autonomy-optional.json`
- `artifacts/proof/frontend.json`
- `artifacts/proof/release_quarantine_hysight45.md`

---

## Environment

- Platform: macOS, local repo `.venv`
- Python: repo-local `.venv` bootstrap
- Rust: sidecar not invoked (carry-forward from hysight-42)
- Node: per `scripts/run_tests.py --frontend`
- Yarn: per `scripts/run_tests.py --frontend`

---

## Seal Conditions

- [x] All baseline tests pass (123/0)
- [x] All autonomy tests pass (66/0, +5 workspace tests)
- [x] Frontend proof passes (67/0, all 5 stages)
- [ ] Live sidecar proof — CARRY-FORWARD from hysight-42 (13/0, no sidecar code changed)

This seal documents the local-core proven state for commit `189980254f92214198fff7d561ca0405c7ccce82`.
Any uncommitted change invalidates the seal.
