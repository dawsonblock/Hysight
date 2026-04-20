# Hysight-36 Optional Proof Summary

**Release tag:** hysight-36
**Commit:** `78b5affefe6780694e69512e14e75038fda68dee`
**Sealed at:** 2026-04-20T22:50:28Z

---

## Autonomy Suite (Optional — Re-run and Passing)

| Metric | Value |
|--------|-------|
| Passed | 61 |
| Failed | 0 |
| Outcome | ✅ PASS |
| Receipt | `artifacts/proof/autonomy-optional.json` |
| Commit | `78b5affefe6780694e69512e14e75038fda68dee` |
| Timestamp | 2026-04-20T22:50:28Z |

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
| Commit | `78b5affefe6780694e69512e14e75038fda68dee` |
| Timestamp | 2026-04-20T22:42:08Z |
| Sidecar engine | `tantivy-bm25+hnsw` |

---

## No-Fallback Verification

- Sidecar at port 3032 was terminated after proof run.
- Backend not running as standalone service — no-fallback status: **N/A** (structural enforcement via `MEMORY_BACKEND=rust` in test env).
- See `artifacts/proof/release_sidecar_no_fallback_hysight36.txt`.

---

## Frontend (UNPROVEN)

Frontend proof is **explicitly UNPROVEN** for hysight-36. `frontend.json` is stale (commit_sha `"local-worktree"`, generated 2026-04-19). Node 20.x unavailable on seal host (v25.9.0 installed).
