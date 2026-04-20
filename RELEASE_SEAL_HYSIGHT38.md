# Hysight-38 Release Seal

**Release tag:** hysight-38
**Commit:** `63dca12e5cb4216e0a0b1bb47c1c9b0baa29704d`
**Repo fingerprint:** `680f036748f4f78becfda70e7ddb9d1945123704`
**Sealed at:** 2026-04-20T23:35:00Z
**Classification:** **sealed full release**

---

## Proof Counts

| Suite | Passed | Failed |
|-------|--------|--------|
| Baseline (pipeline + backend + contract) | 123 | 0 |
| Autonomy | 61 | 0 |
| Frontend | 20 | 0 |
| Live sidecar | 13 | 0 |
| **Total** | **217** | **0** |

Frontend: **PROVEN** — Node 24.15.0 (19 Jest + 1 fixture-drift), all 5 stages passed.

---

## Receipt Hashes

| Receipt | Commit | Timestamp |
|---------|--------|-----------|
| `baseline.json` | `63dca12e5cb4` | 2026-04-20T23:31:17Z |
| `autonomy-optional.json` | `63dca12e5cb4` | 2026-04-20T23:31:38Z |
| `frontend.json` | `63dca12e5cb4` | 2026-04-20T23:29:44Z |
| `live-sidecar.json` | `63dca12e5cb4` | 2026-04-20T23:34:31Z |

---

## Environment

- Platform: macOS 26.2, arm64 (Apple M2 Pro)
- Python: 3.9.7
- Rust: 1.94.0
- Node: v24.15.0 (npm v11.12.1, Yarn 1.22.22)
- Sidecar engine: `tantivy-bm25+hnsw`

---

## Seal Conditions

- [x] All baseline tests pass (123/0)
- [x] All autonomy tests pass (61/0)
- [x] All live sidecar tests pass (13/0, 2 skipped for supervisorctl)
- [x] All receipts regenerated from commit `63dca12e5cb4`
- [x] Quarantine ledger written
- [x] Frontend proof — 20/0 (Node 24.15.0, 5 stages: runtime-verification, fixture-drift, lint, jest, build)

This seal is valid for the exact commit `63dca12e5cb4216e0a0b1bb47c1c9b0baa29704d`. Any uncommitted change invalidates the seal.
