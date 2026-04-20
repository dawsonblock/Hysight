# Hysight-38 Optional Proof Summary

**Release tag:** hysight-38
**Commit:** `63dca12e5cb4216e0a0b1bb47c1c9b0baa29704d`
**Sealed at:** 2026-04-20T23:35:00Z

---

## Autonomy Suite (Optional — Re-run and Passing)

| Metric | Value |
|--------|-------|
| Passed | 61 |
| Failed | 0 |
| Outcome | ✅ PASS |
| Receipt | `artifacts/proof/autonomy-optional.json` |
| Commit | `63dca12e5cb4216e0a0b1bb47c1c9b0baa29704d` |
| Timestamp | 2026-04-20T23:31:38Z |

The autonomy suite exercises the bounded operator-style control layer (`hca/src/hca/autonomy/`), including `style_profile.py`, `attention_controller.py`, and `supervisor.py`. Per the module's own docstring, these profiles describe controllable work-style biases (prioritization, memory emphasis, re-anchoring) and explicitly are not medical or diagnostic behavior models.

---

## Live Sidecar Suite (Optional — Re-run and Passing)

| Metric | Value |
|--------|-------|
| Passed | 13 |
| Skipped | 2 (supervisorctl not in PATH) |
| Failed | 0 |
| Outcome | ✅ PASS |
| Receipt | `artifacts/proof/live-sidecar.json` |
| Commit | `63dca12e5cb4216e0a0b1bb47c1c9b0baa29704d` |
| Timestamp | 2026-04-20T23:34:31Z |
| Sidecar engine | `tantivy-bm25+hnsw` |

---

## No-Fallback Verification

- Sidecar ran at port 3035 (port 3031 was in use on seal host).
- Backend not running as standalone service — no-fallback status: **N/A** (structural enforcement via `MEMORY_BACKEND=rust` in test env).
- See `artifacts/proof/release_sidecar_no_fallback_hysight38.txt`.

---

## Frontend (PROVEN)

| Metric | Value |
|--------|-------|
| Passed | 20 |
| Failed | 0 |
| Outcome | ✅ PASS |
| Receipt | `artifacts/proof/frontend.json` |
| Commit | `63dca12e5cb4216e0a0b1bb47c1c9b0baa29704d` |
| Timestamp | 2026-04-20T23:29:44Z |
| Node | v24.15.0 |

All 5 stages passed: runtime-verification, fixture-drift, lint, jest, build. Frontend was UNPROVEN at initial hysight-38 seal (Node 25.x present); re-proved after upgrading pin from 20 → 24 and installing Node 24.15.0 via nvm.
