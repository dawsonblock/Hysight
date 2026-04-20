# Hysight-36 Full Proof Summary

**Release tag:** hysight-36
**Commit:** `78b5affefe6780694e69512e14e75038fda68dee`
**Repo fingerprint:** `49ea69aec5af3ff97aa93e07031d5bd5ae2350da`
**Sealed at:** 2026-04-20T22:50:28Z
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
| **Frontend** | **UNPROVEN** | — | — | `frontend.json` STALE | Node 20.x unavailable; do not cite |

**Total proven passing tests: 197** (123 baseline + 61 autonomy + 13 sidecar)

---

## Environment

- Python: 3.9.7
- Rust: 1.94.0 (sidecar was running during Phase 2 proof; stopped after no-fallback test)
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
| `artifacts/proof/baseline.json` | `78b5affefe` | 2026-04-20T22:54:19Z | 123 |
| `artifacts/proof/autonomy-optional.json` | `78b5affefe` | 2026-04-20T22:50:28Z | 61 |
| `artifacts/proof/live-sidecar.json` | `78b5affefe` | 2026-04-20T22:42:08Z | 13 |

All receipts regenerated fresh from commit `78b5affefe` during the hysight-36 sealing run.

---

## Classification Rationale

- Packaging: ✅ PASS (`.pkg-venv` fresh install, `pip install -e '.[dev]'`)
- Bootstrap: ✅ PASS (`make venv`)
- Baseline proof: ✅ 123/0
- Autonomy proof: ✅ 61/0
- Sidecar proof: ✅ 13/0 (2 skipped, supervisorctl)
- Frontend proof: ❌ UNPROVEN (Node 20.x unavailable)

Classification is `sealed local-core release` (not `sealed full release`). Frontend must be reproduced on a Node 20.x host to achieve full classification.

---

## Quarantine Reference

See `artifacts/proof/release_quarantine_hysight36.md` for the full ledger of historical documents and stale receipts excluded from this proof.
