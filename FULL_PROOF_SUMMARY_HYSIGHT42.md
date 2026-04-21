# Hysight-42 Full Proof Summary

**Release tag:** hysight-42
**Base commit:** `10966b3bc57905b298563145dba8450d610f9c1c`
**Sealed at:** 2026-04-21T05:54:25Z
**Platform:** external clean-directory verification, repo-local `.venv`
**Classification:** **sealed local-core release**

---

## Proof Matrix

| Suite | Passed | Failed | Skipped | Receipt | Notes |
|-------|--------|--------|---------|---------|-------|
| Pipeline | 7 | 0 | — | *(external run)* | included in baseline total |
| Backend baseline | 98 | 0 | 1 deselected | *(external run)* | included in baseline total |
| Contract | 18 | 0 | — | *(external run)* | included in baseline total |
| **Baseline total** | **123** | **0** | — | *(external run)* | ✅ |
| Autonomy (optional) | 61 | 0 | — | *(external run)* | ✅ style-layer proved |
| Live sidecar | **UNPROVEN** | — | — | — | not re-run in this sealing pass |
| Frontend | **UNPROVEN** | — | — | — | not re-run in this sealing pass |

**Total proven passing tests: 184** (123 baseline + 61 autonomy)

---

## What Was Verified

Proof ran in a clean external directory (unpacked from `Hysight-main 42.zip`), not inside
the live repo. The following surfaces were confirmed:

- Root meta-project packaging (`pip install -e '.[dev]'` in fresh `.pkg-venv`) — PASS
- Supported `.venv` bootstrap — PASS
- Canonical baseline proof: pipeline 7 + backend-baseline 98 + contract 18 = 123/0
- Bounded autonomy + style-layer: 61/0

## What Was Not Verified

- Live Rust sidecar (`memvid-sidecar`, `tantivy-bm25+hnsw`) — not re-run in this pass
- Frontend (Node/Yarn, runtime-verification + fixture-drift + lint + jest + build) — not re-run in this pass

---

## Environment

- Verification mode: clean external unzip
- Python: repo-local `.venv`
- Rust: not invoked in this pass
- Node: not invoked in this pass

---

## Style Layer

The bounded operator-style control layer is present in `hca/src/hca/autonomy/` and exercised
by all 61 autonomy tests.

Files: `style_profile.py`, `attention_controller.py`, `supervisor.py` (and sibling modules).

`style_profile.py` explicitly limits itself to controllable work-style biases for
prioritization, memory emphasis, and re-anchoring within a bounded policy surface. It does
not model human-equivalent intelligence, medical diagnosis, or clinical behavior.

---

## What Materially Changed vs hysight-41

42 keeps the strong 34–41 state intact without introducing a new major subsystem beyond the
already-proved bounded style layer. The verified carry-forward surfaces remain:

- bounded autonomy
- style profiles
- attention controller
- re-anchor engine
- style-aware supervisor integration
- style-aware checkpoints and routes
- one execution authority through ordinary HCA runs

---

## Classification Rationale

- Packaging: ✅ PASS
- Baseline proof: ✅ 123/0
- Autonomy proof: ✅ 61/0
- Sidecar proof: ❌ UNPROVEN (not re-run)
- Frontend proof: ❌ UNPROVEN (not re-run)

Classification is `sealed local-core release`. To achieve `sealed full-proof release`,
re-run the live sidecar proof and frontend proof on matching toolchains and update this
document with fresh 42-specific evidence.