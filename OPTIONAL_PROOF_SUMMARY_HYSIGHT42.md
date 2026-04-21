# Hysight-42 Optional Proof Summary

**Release tag:** hysight-42
**Base commit:** `10966b3bc57905b298563145dba8450d610f9c1c`
**Sealed at:** 2026-04-21T05:54:25Z

---

## Autonomy Suite (Optional — Re-run and Passing)

| Metric | Value |
|--------|-------|
| Passed | 61 |
| Failed | 0 |
| Outcome | ✅ PASS |
| Receipt | *(external clean-directory run)* |
| Commit | `10966b3bc57905b298563145dba8450d610f9c1c` |

The autonomy suite exercises the bounded operator-style control layer
(`hca/src/hca/autonomy/`), including `style_profile.py`, `attention_controller.py`,
and `supervisor.py`. Per the module's own docstring, these profiles describe controllable
work-style biases (prioritization, memory emphasis, re-anchoring) and explicitly are not
medical or diagnostic behavior models.

---

## Live Sidecar Suite (UNPROVEN)

Live sidecar proof was not run in this sealing pass. The sidecar binary and engine
(`tantivy-bm25+hnsw`) were not invoked. To prove this surface, start `memvid-sidecar`
on an available port using `MEMORY_SERVICE_PORT=<port>` and run
`.venv/bin/python scripts/proof_sidecar.py` or the repo-supported sidecar proof path.

Previous in-repo proof reference: hysight-41 sidecar 13/0 on commit `00ac02424827`.

---

## Frontend (UNPROVEN)

Frontend proof was not run in this sealing pass. Node/Yarn toolchain was not invoked.
Frontend currently enforces Node 24.x and Yarn 1.22.22.

To prove this surface, ensure the exact supported runtime is active and run
`yarn --cwd frontend install --frozen-lockfile` followed by
`.venv/bin/python scripts/proof_frontend.py`.

Previous in-repo proof reference: hysight-41 frontend 20/0 on commit `00ac02424827`,
Node 24.15.0, all 5 stages passed.