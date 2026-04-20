# Hysight-36 Release Seal

**Release tag:** hysight-36
**Commit:** `78b5affefe6780694e69512e14e75038fda68dee`
**Repo fingerprint:** `49ea69aec5af3ff97aa93e07031d5bd5ae2350da`
**Sealed at:** 2026-04-20T22:50:28Z
**Classification:** **sealed local-core release**

---

## Proof Counts

| Suite | Passed | Failed |
|-------|--------|--------|
| Baseline (pipeline + backend + contract) | 123 | 0 |
| Autonomy | 61 | 0 |
| Live sidecar | 13 | 0 |
| **Total** | **197** | **0** |

Frontend: **UNPROVEN** — Node 20.x unavailable at seal time.

---

## Receipt Hashes

| Receipt | Commit | Timestamp |
|---------|--------|-----------|
| `baseline.json` | `78b5affefe` | 2026-04-20T22:54:19Z |
| `autonomy-optional.json` | `78b5affefe` | 2026-04-20T22:50:28Z |
| `live-sidecar.json` | `78b5affefe` | 2026-04-20T22:42:08Z |

---

## Environment

- Platform: macOS 26.2, arm64 (Apple M2 Pro)
- Python: 3.9.7
- Rust: 1.94.0
- Node: v25.9.0 (frontend pins 20.x — skipped)
- Sidecar engine: `tantivy-bm25+hnsw`

---

## Seal Conditions

- [x] All baseline tests pass (123/0)
- [x] All autonomy tests pass (61/0)
- [x] All live sidecar tests pass (13/0, 2 skipped for supervisorctl)
- [x] All receipts regenerated from commit `78b5affefe`
- [x] Quarantine ledger written
- [ ] Frontend proof — UNPROVEN (requires Node 20.x host)

This seal is valid for the exact commit `78b5affefe6780694e69512e14e75038fda68dee`. Any uncommitted change invalidates the seal.
