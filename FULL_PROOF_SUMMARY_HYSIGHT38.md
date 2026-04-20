# Hysight-38 Full Proof Summary

**Release tag:** hysight-38
**Commit:** `63dca12e5cb4216e0a0b1bb47c1c9b0baa29704d`
**Repo fingerprint:** `680f036748f4f78becfda70e7ddb9d1945123704`
**Sealed at:** 2026-04-20T23:35:00Z
**Platform:** macOS 26.2, arm64 (Apple M2 Pro), Python 3.9.7, Node 24.15.0
**Classification:** **sealed full release**

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
| **Frontend** | **20** | **0** | — | `frontend.json` | ✅ Node 24.15.0, 5 stages passed |

**Total proven passing tests: 217** (123 baseline + 61 autonomy + 20 frontend + 13 sidecar)

---

## Environment

- Python: 3.9.7
- Rust: 1.94.0 (sidecar was running during Phase 2 proof; port 3032 used, port 3031 in use)
- Node: v24.15.0 (npm v11.12.1, Yarn 1.22.22)
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
| `artifacts/proof/baseline.json` | `63dca12e5cb4` | 2026-04-20T23:31:17Z | 123 |
| `artifacts/proof/autonomy-optional.json` | `63dca12e5cb4` | 2026-04-20T23:31:38Z | 61 |
| `artifacts/proof/frontend.json` | `63dca12e5cb4` | 2026-04-20T23:29:44Z | 20 |
| `artifacts/proof/live-sidecar.json` | `63dca12e5cb4` | 2026-04-20T23:34:31Z | 13 |

All receipts regenerated fresh from commit `63dca12e5cb4` during the hysight-38 sealing run.

---

## Classification Rationale

- Packaging: ✅ PASS (`.venv` install, `pip install -e '.[dev]'`)
- Baseline proof: ✅ 123/0
- Autonomy proof: ✅ 61/0
- Frontend proof: ✅ 20/0 (Node 24.15.0, 5 stages: runtime-verification, fixture-drift, lint, jest, build)
- Sidecar proof: ✅ 13/0 (2 skipped, supervisorctl)

Classification is `sealed full release`. All four proof surfaces passing.

---

## Quarantine Reference

See `artifacts/proof/release_quarantine_hysight38.md` for the full ledger of historical documents excluded from this proof.
