# Hysight-42 Full Proof Summary

**Release tag:** hysight-42
**Base commit:** `10966b3bc57905b298563145dba8450d610f9c1c`
**Sealed at:** 2026-04-21T06:18:48Z
**Platform:** mixed proof sources for the exact base commit
**Classification:** **sealed full-proof release**

---

## Proof Matrix

| Suite | Passed | Failed | Skipped | Receipt | Notes |
|-------|--------|--------|---------|---------|-------|
| Pipeline | 7 | 0 | — | *(external run)* | included in baseline total |
| Backend baseline | 98 | 0 | 1 deselected | *(external run)* | included in baseline total |
| Contract | 18 | 0 | — | *(external run)* | included in baseline total |
| **Baseline total** | **123** | **0** | — | *(external run)* | ✅ |
| Autonomy (optional) | 61 | 0 | — | *(external run)* | ✅ style-layer proved |
| Live sidecar | 13 | 0 | 2 skipped | `artifacts/proof/release_live_sidecar_receipt_hysight42.json` | ✅ exact-commit detached worktree rerun |
| Frontend | 20 | 0 | — | `artifacts/proof/release_frontend_receipt_hysight42.json` | ✅ exact-commit detached worktree rerun |

**Total proven passing tests: 217** (123 baseline + 61 autonomy + 13 sidecar + 20 frontend)

Additive sidecar parity evidence also passed: 4/0 via `backend/tests/test_memvid_sidecar_parity.py --run-live`.

---

## What Was Verified

Proof for the exact base commit came from two fresh sources on 2026-04-21:

- clean external directory verification (unpacked from `Hysight-main 42.zip`) for packaging, bootstrap, baseline, and autonomy
- isolated detached worktree at commit `10966b3bc57905b298563145dba8450d610f9c1c` for live sidecar and frontend reruns

The following surfaces were confirmed:

- Root meta-project packaging (`pip install -e '.[dev]'` in fresh `.pkg-venv`) — PASS
- Supported `.venv` bootstrap — PASS
- Canonical baseline proof: pipeline 7 + backend-baseline 98 + contract 18 = 123/0
- Bounded autonomy + style-layer: 61/0
- Live Rust sidecar (`memvid-sidecar`, `tantivy-bm25+hnsw`) — 13 passed, 2 skipped on fallback port `3032`
- Live sidecar parity — 4 passed, 0 failed
- Sidecar no-fallback startup check — PASS (`artifacts/proof/release_sidecar_no_fallback_hysight42.txt`)
- Frontend (runtime-verification + fixture-drift + lint + jest + build) — 20/0 on Node `24.15.0` and Yarn `1.22.22`

---

## Environment

- Verification modes:
	- clean external unzip for local-core proof
	- detached worktree for exact-commit optional proof
- Python: repo-local `.venv`
- Rust: cargo 1.94.0
- Node: 24.15.0
- Yarn: 1.22.22

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
- Sidecar proof: ✅ 13/0 with 2 expected skips
- Sidecar parity: ✅ 4/0 additive evidence
- Sidecar fail-closed startup: ✅ PASS
- Frontend proof: ✅ 20/0

Classification is `sealed full-proof release` because every release-facing proof surface for
the exact `10966b3bc57905b298563145dba8450d610f9c1c` target now has fresh 42-specific
evidence.