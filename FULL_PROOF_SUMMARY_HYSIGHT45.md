# Hysight-45 Full Proof Summary

**Release tag:** hysight-45
**Commit:** `189980254f92214198fff7d561ca0405c7ccce82`
**Sealed at:** 2026-04-21T23:03:15Z
**Platform:** macOS, local repo `.venv`
**Classification:** **sealed local-core release**

---

## Proof Matrix

| Suite | Passed | Failed | Skipped | Receipt | Notes |
|-------|--------|--------|---------|---------|-------|
| Pipeline | 7 | 0 | — | *(local run)* | included in baseline total |
| Backend baseline | 98 | 0 | 1 deselected | *(local run)* | included in baseline total |
| Contract | 18 | 0 | — | *(local run)* | included in baseline total |
| **Baseline total** | **123** | **0** | — | *(local run)* | ✅ |
| Autonomy (optional) | 66 | 0 | — | *(local run)* | ✅ +5 workspace tests |
| Frontend | 67 | 0 | — | *(local run)* | ✅ all 5 stages |
| Live sidecar | **UNPROVEN** | — | — | — | not re-run in this pass |

**Total proven passing tests: 256** (123 baseline + 66 autonomy + 67 frontend)

---

## What Was Verified

Proof ran against the live repo at commit `189980254f92214198fff7d561ca0405c7ccce82`.
The following surfaces were confirmed:

- Canonical baseline proof: pipeline 7 + backend-baseline 98 + contract 18 = 123/0
- Bounded autonomy + aggregate workspace route: 66/0 (was 61; +5 workspace tests)
- Frontend (runtime-verification + fixture-drift + lint + Jest + production build): 67/0

## What Was Not Verified

- Live Rust sidecar (`memvid-sidecar`, tantivy-bm25+hnsw engine) — not re-run in this pass  
  Last proven: hysight-42, commit `10966b3bc57905b298563145dba8450d610f9c1c`, 13/0

---

## Environment

- Python: repo-local `.venv`
- Rust: sidecar not invoked
- Node: per frontend proof pass (`scripts/run_tests.py --frontend`)
- Yarn: per frontend proof pass

---

## Style Layer

The bounded operator-style control layer is present in `hca/src/hca/autonomy/` and exercised
by all 66 autonomy tests.

Files: `style_profile.py`, `attention_controller.py`, `supervisor.py` (and sibling modules).

`style_profile.py` explicitly limits itself to controllable work-style biases for
prioritization, memory emphasis, and re-anchoring within a bounded policy surface. It does
not model medical, diagnostic, or clinical behavior.

---

## What Materially Changed vs hysight-42

### Phase A — Aggregate backend endpoint

Added `GET /api/hca/autonomy/workspace` which returns an `AutonomyWorkspaceSnapshot`
containing all 9 data sections (status, agents, schedules, inbox, runs, escalations,
budgets, checkpoints, section_errors) in a single round-trip. Uses `asyncio.gather` with
`return_exceptions=True` so one slow section does not block the others.

Files changed:
- `backend/server_models.py` — `AutonomyWorkspaceSnapshot` class + `model_rebuild()`
- `backend/server_autonomy_routes.py` — full workspace route with `_SECTIONS` gather pattern
- `backend/tests/test_autonomy_routes.py` — 5 new workspace tests

### Phase B — Frontend single-fetch migration

Replaced 8-resource polling in `useAutonomyPolling.js` with a single `getAutonomyWorkspace()` call.
Added `autonomyWorkspaceSnapshotSchema` and `getAutonomyWorkspace()` to the Zod-validated API client.
Updated `AutonomyWorkspace.test.js` and `autonomy-api.test.js` to cover the new surface.
Regenerated `api.fixtures.generated.json` (now includes `run_status`, `last_state`, `last_decision`
from the pre-existing `AutonomyRunLinkResponse` model).
Updated `contract/schema.json` (`AutonomyRunLinkSummary`) to allow those 3 fields.

Files changed:
- `frontend/src/lib/autonomy-api.js` — schema + `getAutonomyWorkspace()`
- `frontend/src/features/autonomy/useAutonomyPolling.js` — single-fetch migration
- `frontend/src/lib/autonomy-api.test.js` — 1 new API test
- `frontend/src/features/autonomy/AutonomyWorkspace.test.js` — mocks updated
- `frontend/src/lib/api.fixtures.generated.json` — regenerated
- `contract/schema.json` — `AutonomyRunLinkSummary` extended with 3 optional fields

---

## Classification Rationale

Baseline and autonomy proofs ran locally at the exact commit. Frontend proof passed all
5 stages (runtime-verify, fixture-drift, lint, Jest 67/0, production build). Live Rust
sidecar was not re-run; last proof stands from hysight-42. Classification is therefore
"sealed local-core release" — core Python + frontend surfaces are proved; sidecar is
carry-forward.
