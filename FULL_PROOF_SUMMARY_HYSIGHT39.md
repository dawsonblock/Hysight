# Hysight-39 Full Proof Summary

**Release tag:** hysight-39
**Commit:** `667fc47bbf1d860d7076c98bd81f1438d38d9ef9`
**Sealed at:** 2026-04-21T04:44:54Z
**Platform:** macOS, clean container verify, Python repo `.venv`
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
| Live sidecar | **UNPROVEN** | — | — | — | not re-run in this pass |
| Frontend | **UNPROVEN** | — | — | — | not re-run in this pass |

**Total proven passing tests: 184** (123 baseline + 61 autonomy)

---

## What Was Verified

Proof ran in a clean external directory (unpacked from `Hysight-main 39.zip`), not inside
the live repo. The following surfaces were confirmed:

- Root meta-project packaging (`pip install -e '.[dev]'` in fresh `.pkg-venv`) — PASS
- Supported `.venv` bootstrap — PASS
- Canonical baseline proof: pipeline 7 + backend-baseline 98 + contract 18 = 123/0
- Bounded autonomy + style-layer: 61/0

## What Was Not Verified

- Live Rust sidecar (`memvid-sidecar`, tantivy-bm25+hnsw engine) — not invoked
- Frontend (Node/Yarn, Jest + build pipeline) — not invoked

---

## Environment

- Python: 3.9.7 (repo `.venv`)
- Rust: sidecar not invoked
- Node: not invoked

---

## Style Layer

The bounded operator-style control layer is present in `hca/src/hca/autonomy/` and exercised
by all 61 autonomy tests.

Files: `style_profile.py`, `attention_controller.py`, `supervisor.py` (and sibling modules).

`style_profile.py` explicitly limits itself to controllable work-style biases for
prioritization, memory emphasis, and re-anchoring within a bounded policy surface. It does
not model medical, diagnostic, or clinical behavior.

---

## What Materially Changed vs hysight-38

39 is a clean carry-forward of the strong 34–38 state. No new major subsystem was added
beyond the already-proved style layer. It preserves:

- bounded autonomy
- style profiles
- attention controller
- re-anchor engine
- kill switch, budgets, dedupe, checkpoints
- one execution authority through ordinary HCA runs

---

## Classification Rationale

- Packaging: ✅ PASS
- Baseline proof: ✅ 123/0
- Autonomy proof: ✅ 61/0
- Sidecar proof: ❌ UNPROVEN (not run)
- Frontend proof: ❌ UNPROVEN (not run)

Classification is `sealed local-core release`. To achieve `sealed full release`, re-run
the live sidecar proof and frontend proof on matching toolchains and update this document.
