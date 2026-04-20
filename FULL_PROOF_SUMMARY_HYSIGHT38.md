# Hysight-38 Full Proof Summary

**Release tag:** hysight-38
**Commit:** `9a1bb3274476c0e7ea7e1af818ede4f235a5a51e`
**Repo fingerprint:** `680f036748f4f78becfda70e7ddb9d1945123704`
**Sealed at:** 2026-04-20T23:15:53Z
**Platform:** macOS 26.2, arm64 (Apple M2 Pro), Python 3.9.7
**Classification:** **sealed local-core release**

---

## Proof Matrix

| Suite | Passed | Failed | Skipped | Receipt | Notes |
|-------|--------|--------|---------|---------|-------|
| Pipeline | 7 | 0 | — | `baseline.json` | included in baseline total |
| Backend baseline | 98 | 0 | — | `baseline.json` | included in baseline total |
| Contract | 18 | 0 | — | `baseline.json` | included in baseline total |
| **Baseline total** | **123** | **0** | — | `baseline.json` | ✅ |
| Autonomy (optional) | 61 | 0 | — | `autonomy-optional.json` | ✅ |
| Live sidecar | 13 | 0 | 2 | `live-sidecar.json` | 2 skipped: supervisorctl not in PATH |
| **Frontend** | **UNPROVEN** | — | — | — | Node 20.x unavailable; do not cite |

**Total proven passing tests: 197** (123 baseline + 61 autonomy + 13 sidecar)

---

## Environment

- Python: 3.9.7
- Rust: 1.94.0 (sidecar was running during Phase 2 proof; port 3032 used, port 3031 in use)
- Node: v25.9.0 (frontend pins 20.x — proof skipped)
- Yarn: 1.22.22
- Sidecar engine: `tantivy-bm25+hnsw`

---

## Style Layer

The bounded operator-style control layer is present in `hca/src/hca/autonomy/` and exercised by all 61 autonomy tests.

Files: `style_profile.py`, `attention_controller.py`, `supervisor.py` (and sibling modules).

Note: `style_profile.py` explicitly limits itself to controllable work-style biases for prioritization, memory emphasis, and re-anchoring within a bounded policy surface. It does not model medical, diagnostic, or clinical behavior.

---

## Receipts Summary

| Receipt file | Commit | Timestamp | Passed |
|-------------|--------|-----------|--------|
| `artifacts/proof/baseline.json` | `9a1bb32744` | 2026-04-20T23:15:46Z | 123 |
| `artifacts/proof/autonomy-optional.json` | `9a1bb32744` | 2026-04-20T23:15:53Z | 61 |
| `artifacts/proof/live-sidecar.json` | `9a1bb32744` | 2026-04-20T23:14:41Z | 13 |

All receipts regenerated fresh from commit `9a1bb32744` during the hysight-38 sealing run.

---

## Classification Rationale

- Packaging: ✅ PASS (`.venv` install, `pip install -e '.[dev]'`)
- Baseline proof: ✅ 123/0
- Autonomy proof: ✅ 61/0
- Sidecar proof: ✅ 13/0 (2 skipped, supervisorctl)
- Frontend proof: ❌ UNPROVEN (Node 20.x unavailable)

Classification is `sealed local-core release` (not `sealed full release`). Frontend must be reproduced on a Node 20.x host to achieve full classification.

---

## Quarantine Reference

See `artifacts/proof/release_quarantine_hysight38.md` for the full ledger of historical documents excluded from this proof.
