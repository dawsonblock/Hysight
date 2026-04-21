# Hysight-45 Optional Proof Summary

**Release tag:** hysight-45
**Commit:** `189980254f92214198fff7d561ca0405c7ccce82`
**Sealed at:** 2026-04-21T23:03:15Z

---

## Autonomy Suite (Optional — Re-run and Passing)

| Metric | Value |
|--------|-------|
| Passed | 66 |
| Failed | 0 |
| Outcome | ✅ PASS |
| Receipt | *(local run)* |
| Commit | `189980254f92214198fff7d561ca0405c7ccce82` |

The autonomy suite exercises the bounded operator-style control layer
(`hca/src/hca/autonomy/`), including `style_profile.py`, `attention_controller.py`,
and `supervisor.py`. Per the module's own docstring, these profiles describe controllable
work-style biases (prioritization, memory emphasis, re-anchoring) and explicitly are not
medical or diagnostic behavior models.

5 new workspace tests were added in hysight-45:
- `test_workspace_snapshot_empty_state`
- `test_workspace_snapshot_agent_and_schedule_present`
- `test_workspace_snapshot_run_status_fields_present`
- `test_workspace_snapshot_kill_switch_visible`
- `test_workspace_snapshot_escalation_in_section`

---

## Frontend Suite (Re-run and Passing)

| Metric | Value |
|--------|-------|
| Passed | 67 |
| Failed | 0 |
| Outcome | ✅ PASS |
| Receipt | *(local run)* |

Frontend proof passed all 5 stages via `scripts/run_tests.py --frontend`:

1. **Runtime verification** — backend endpoints callable, subsystems healthy
2. **Fixture drift gate** — `api.fixtures.generated.json` matches committed snapshot
3. **Lint** — ESLint clean
4. **Jest** — 67 tests passing across all suites (was 20 prior to hysight-45 frontend expansion)
5. **Production build** — `craco build` succeeded

Frontend changes in hysight-45:
- `getAutonomyWorkspace()` in `autonomy-api.js` with `autonomyWorkspaceSnapshotSchema`
- `useAutonomyPolling.js` migrated from 8-resource polling to single aggregate fetch
- `autonomy-api.test.js` +1 test for the new endpoint
- `AutonomyWorkspace.test.js` mock updated to `getAutonomyWorkspace`
- `api.fixtures.generated.json` regenerated (now includes `run_status`, `last_state`, `last_decision`)

---

## Live Sidecar Suite

| Metric | Value |
|--------|-------|
| Status | **CARRY-FORWARD** |
| Last proven | hysight-42, commit `10966b3bc57905b298563145dba8450d610f9c1c` |
| Last result | 13 passed, 0 failed, 2 skipped |
| Receipt | `artifacts/proof/release_live_sidecar_receipt_hysight42.json` |

Live Rust sidecar was not re-run in the hysight-45 sealing pass. No sidecar code was
modified between hysight-42 and hysight-45.
