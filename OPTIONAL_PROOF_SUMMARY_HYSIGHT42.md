# Hysight-42 Optional Proof Summary

**Release tag:** hysight-42
**Base commit:** `10966b3bc57905b298563145dba8450d610f9c1c`
**Sealed at:** 2026-04-21T06:18:48Z

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

## Live Sidecar Suite (Re-run and Passing)

| Metric | Value |
|--------|-------|
| Passed | 13 |
| Failed | 0 |
| Skipped | 2 |
| Outcome | ✅ PASS |
| Receipt | `artifacts/proof/release_live_sidecar_receipt_hysight42.json` |
| Service endpoint | `http://localhost:3032` |

Live sidecar proof was re-run in an isolated detached worktree at the exact base commit.
The proof auto-fell forward from occupied port `3031` to healthy fallback port `3032` and
completed successfully against the Rust sidecar engine (`tantivy-bm25+hnsw`).

Additive sidecar parity evidence also passed: 4/0 via
`backend/tests/test_memvid_sidecar_parity.py -q --run-live -ra`.

Fail-closed startup behavior was refreshed separately and passed: with
`MEMORY_BACKEND=rust` and an unreachable `MEMORY_SERVICE_URL`, `scripts/run_backend.sh`
exited non-zero instead of falling back to local memory. Evidence lives in
`artifacts/proof/release_sidecar_no_fallback_hysight42.txt`.

Previous in-repo proof reference: hysight-41 sidecar 13/0 on commit `00ac02424827`.

---

## Frontend (Re-run and Passing)

| Metric | Value |
|--------|-------|
| Passed | 20 |
| Failed | 0 |
| Outcome | ✅ PASS |
| Receipt | `artifacts/proof/release_frontend_receipt_hysight42.json` |
| Runtime | Node `24.15.0`, Yarn `1.22.22` |

Frontend proof was re-run in the same detached worktree for the exact base commit. All
five frontend stages passed:

- runtime verification
- fixture drift gate
- lint
- Jest
- production build

Previous in-repo proof reference: hysight-41 frontend 20/0 on commit `00ac02424827`,
Node 24.15.0, all 5 stages passed.