# Hysight-39 Optional Proof Summary

**Release tag:** hysight-39
**Commit:** `667fc47bbf1d860d7076c98bd81f1438d38d9ef9`
**Sealed at:** 2026-04-21T04:44:54Z

---

## Autonomy Suite (Optional — Re-run and Passing)

| Metric | Value |
|--------|-------|
| Passed | 61 |
| Failed | 0 |
| Outcome | ✅ PASS |
| Receipt | *(external clean-directory run)* |
| Commit | `667fc47bbf1d860d7076c98bd81f1438d38d9ef9` |

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
`.venv/bin/python scripts/run_tests.py --sidecar`.

Previous proof reference: hysight-38 sidecar 13/0 on commit `af16597554ff`.

---

## Frontend (UNPROVEN)

Frontend proof was not run in this sealing pass. Node/Yarn toolchain was not invoked.
Frontend pins Node 24.x (see `frontend/.nvmrc`, `frontend/package.json`).

To prove this surface, ensure Node 24.x is active (e.g. `nvm use 24`) and run
`.venv/bin/python scripts/proof_frontend.py`.

Previous proof reference: hysight-38 frontend 20/0 on commit `af16597554ff`,
Node 24.15.0, all 5 stages passed (runtime-verification, fixture-drift, lint, jest, build).
