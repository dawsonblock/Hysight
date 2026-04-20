# Hysight-38 Optional Proof Summary

**Release tag:** hysight-38
**Commit:** `9a1bb3274476c0e7ea7e1af818ede4f235a5a51e`
**Sealed at:** 2026-04-20T23:15:53Z

---

## Autonomy Suite (Optional — Re-run and Passing)

| Metric | Value |
|--------|-------|
| Passed | 61 |
| Failed | 0 |
| Outcome | ✅ PASS |
| Receipt | `artifacts/proof/autonomy-optional.json` |
| Commit | `9a1bb3274476c0e7ea7e1af818ede4f235a5a51e` |
| Timestamp | 2026-04-20T23:15:53Z |

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
| Commit | `9a1bb3274476c0e7ea7e1af818ede4f235a5a51e` |
| Timestamp | 2026-04-20T23:14:41Z |
| Sidecar engine | `tantivy-bm25+hnsw` |

---

## No-Fallback Verification

- Sidecar ran at port 3032 (port 3031 was in use on seal host).
- Backend not running as standalone service — no-fallback status: **N/A** (structural enforcement via `MEMORY_BACKEND=rust` in test env).
- See `artifacts/proof/release_sidecar_no_fallback_hysight38.txt`.

---

## Frontend (UNPROVEN)

Frontend proof is **explicitly UNPROVEN** for hysight-38. Node 20.x unavailable on seal host (v25.9.0 installed). Frontend must be run on a Node 20.x host to be proven.
