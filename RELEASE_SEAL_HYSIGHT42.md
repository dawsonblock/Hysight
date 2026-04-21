# Hysight-42 Release Seal

**Release tag:** hysight-42
**Base commit:** `10966b3bc57905b298563145dba8450d610f9c1c`
**Sealed at:** 2026-04-21T06:18:48Z
**Classification:** **sealed full-proof release**

---

## Proof Counts

| Suite | Passed | Failed |
|-------|--------|--------|
| Baseline (pipeline + backend + contract) | 123 | 0 |
| Autonomy | 61 | 0 |
| Live sidecar | 13 | 0 |
| Frontend | 20 | 0 |
| **Total** | **217** | **0** |

Sidecar parity: **4/0 additive evidence**.
Sidecar no-fallback startup: **PASS**.

---

## Evidence Files

Local-core proof for packaging, bootstrap, baseline, and autonomy was executed in a clean
external directory unpacked from `Hysight-main 42.zip`. Optional sidecar and frontend proof
were freshly re-run in a detached worktree at the exact base commit.

- `artifacts/proof/release_live_sidecar_receipt_hysight42.json`
- `artifacts/proof/release_frontend_receipt_hysight42.json`
- `artifacts/proof/release_sidecar_hysight42.log`
- `artifacts/proof/release_sidecar_no_fallback_hysight42.txt`
- `test_reports/frontend-jest-hysight42.json`
- `test_reports/frontend-fixture-drift-hysight42.xml`

---

## Environment

- Platform: clean external unzip plus detached exact-commit worktree
- Python: repo-local `.venv` bootstrap
- Rust: cargo 1.94.0
- Node: 24.15.0
- Yarn: 1.22.22
- `.pkg-venv` contamination fix: verified

---

## Seal Conditions

- [x] Root meta-project packaging installs cleanly (`.pkg-venv`)
- [x] Supported `.venv` bootstrap passes
- [x] All baseline tests pass (123/0)
- [x] All autonomy tests pass (61/0)
- [x] Live sidecar proof passes (13/0, 2 expected skips)
- [x] Frontend proof passes (20/0)

This seal documents the externally verified local-core state for the exact base commit
`10966b3bc57905b298563145dba8450d610f9c1c`, with sidecar and frontend refreshed in a
detached worktree at that same commit.