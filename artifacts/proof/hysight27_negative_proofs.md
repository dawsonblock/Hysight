# Hysight-main 27 negative proofs

## Verdict

**Result: PASS for the negative-proof checks that were exercised.**

The build fails explicitly and safely in the critical scenarios tested below.

## 1. Sidecar-down negative proof

Command outcome:
- With `MEMORY_BACKEND=rust`
- With `MEMORY_SERVICE_URL=http://127.0.0.1:3041`
- And the sidecar stopped

The backend startup path failed explicitly with:

> `MemoryConfigurationError: Rust memory backend health check failed for http://127.0.0.1:3041/health ... Connection refused`

**Conclusion:** no silent fallback to the Python-local memory backend was observed.

## 2. High-risk autonomy continuation

Fresh targeted proof command:
- `./.venv/bin/python -m pytest backend/tests/test_autonomy_policy.py -q -ra -k 'high_risk or escalation or resume_still_blocks_high_risk_class'`

Fresh result:
- **2 passed, 10 deselected**

Meaning:
- high-risk action classes requiring approval escalate instead of proceeding
- resume logic continues to block high-risk classes without approval

## 3. Restart duplicate prevention

Fresh targeted proof command:
- `./.venv/bin/python -m pytest backend/tests/test_autonomy_resume.py backend/tests/test_autonomy_dedupe.py -q -ra`

Fresh result:
- **6 passed**

Meaning:
- restart reloads persisted checkpoints
- the same trigger/dedupe key is observed/resumed rather than launched again

## 4. Kill switch blocks new launches

Fresh targeted proof command:
- `./.venv/bin/python -m pytest backend/tests/test_autonomy_kill_switch.py -q -ra`

Fresh result:
- **3 passed**

Meaning:
- the kill switch rejects new triggers
- continuation is blocked cleanly
- clearing the kill switch restores acceptance

## 5. Artifact-truth spot check

Fresh receipts and proof artifacts were verified present on disk after this run:

- `artifacts/proof/live-sidecar.json`
- `artifacts/proof/frontend.json`
- `artifacts/proof/hysight27_sidecar_proof.txt`
- `artifacts/proof/hysight27_sidecar_no_fallback.txt`
- `test_reports/pytest/backend-live-sidecar-proof.xml`
- `test_reports/frontend-fixture-drift.xml`

These artifacts were not treated as implied; they were checked for actual existence and fresh timestamps.

## Conclusion

The negative cases requested for this audit were exercised fresh on this revision and behaved safely:
explicit failure for a dead sidecar, escalation for high-risk continuation, dedupe on restart, and kill-switch enforcement.