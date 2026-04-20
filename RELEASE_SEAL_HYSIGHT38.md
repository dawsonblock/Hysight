# Hysight-38 Release Seal

**Release tag:** hysight-38
**Commit:** `9a1bb3274476c0e7ea7e1af818ede4f235a5a51e`
**Repo fingerprint:** `680f036748f4f78becfda70e7ddb9d1945123704`
**Sealed at:** 2026-04-20T23:15:53Z
**Classification:** **sealed local-core release**

---

## Proof Counts

| Suite | Passed | Failed |
|-------|--------|--------|
| Baseline (pipeline + backend + contract) | 123 | 0 |
| Autonomy | 61 | 0 |
| Live sidecar | 13 | 0 |
| **Total** | **197** | **0** |

Frontend: **UNPROVEN** — Node 20.x unavailable at seal time (v25.9.0 present).

---

## Receipt Hashes

| Receipt | Commit | Timestamp |
|---------|--------|-----------|
| `baseline.json` | `9a1bb32744` | 2026-04-20T23:15:46Z |
| `autonomy-optional.json` | `9a1bb32744` | 2026-04-20T23:15:53Z |
| `live-sidecar.json` | `9a1bb32744` | 2026-04-20T23:14:41Z |

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
- [x] All receipts regenerated from commit `9a1bb32744`
- [x] Quarantine ledger written
- [ ] Frontend proof — UNPROVEN (requires Node 20.x host)

This seal is valid for the exact commit `9a1bb3274476c0e7ea7e1af818ede4f235a5a51e`. Any uncommitted change invalidates the seal.
