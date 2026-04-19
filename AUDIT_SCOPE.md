# Audit Scope

## Audit preconditions

- **Clean-clone rule.** Run the double-check in a fresh clone or a fresh unzip, never in a dirty working tree. Local state produces both false passes and false failures; any run that starts in a dirty tree is not admissible as a proof.
- **Receipt-freshness rule.** Every proof receipt cited in the report must either be generated in the current run, or be explicitly marked historical and excluded from classification. Copied or carried-over artifacts do not count as evidence for this run.
- **Final-classification rule.** If the baseline is fresh but the optional surfaces (frontend, integration, mongo-live, sidecar, autonomy-optional) have only historical receipts, the build cannot be called hardened for this run. It may only inherit the hardened label after those optional surfaces are re-proved on this exact revision. *Any claimed surface without a fresh passing receipt from this run is unproven, even if bundled receipts exist.*

## Proven by current receipts

- Running `./.venv/bin/python scripts/run_tests.py` on 2026-04-19 refreshed `artifacts/proof/baseline.json` and passed the declared local baseline.
- The current baseline receipt proves the supported service-free authority path only:
  - HCA pipeline proof: 7 passed.
  - Backend baseline proof: 98 passed, 1 deselected.
  - Contract conformance proof: 18 passed.
- That proves the local python-backed memory mode, the repo-local backend runtime surface exercised by `scripts/run_tests.py`, and contract-shape conformance for the declared backend endpoints.
- The baseline receipt is honest about scope. It explicitly omits `frontend`, `integration`, `mongo-live`, and `sidecar`.

## Not proven by current receipts

- A real reachable rust sidecar started through the supported `memvid_service/` path.
- Sidecar parity versus the local python memory authority for live ingest, retrieve, list, delete, maintain, and outage handling.
- Graceful restart persistence or outage/recovery behavior for the sidecar-backed mode.
- Frontend proof on the declared supported toolchain for the current snapshot.
- Clean-start bootstrap and release reproducibility from the published docs and Make targets.
- Bounded concurrency and stress behavior for backend runs, local memory state, and SSE streams.
- Multi-client fan-out for the same existing SSE run stream.

## Negative proofs required

Do not only prove what works. The build must also fail the right way when something critical is missing. Each of the following negative cases must have a fresh receipt in the current run:

- **Sidecar mode with the sidecar down.** With `MEMORY_BACKEND=sidecar` and no reachable `memvid_service`, the backend must fail explicitly on startup or first memory call. Silent fallback to the python authority is a classification-changing failure.
- **Kill switch blocks new launches.** With the autonomy kill switch active, `accept_trigger` must reject with reason `kill_switch_active` and no checkpoint may be written. A launch during active kill-switch is a classification-changing failure.
- **High-risk autonomy continuation must escalate.** When the last `action_selected` event has an `action_class` listed in the agent policy's `approval_required_action_classes`, the evaluator must return `escalate`, the checkpoint must move to `awaiting_approval`, and no continuation event may be emitted. Any proceed-without-approval is a classification-changing failure.

## Route-to-runtime integrity

Autonomy must never bypass the normal run authority path.

- No autonomy route may execute tools directly. Every autonomous run must be created through `Runtime.create_autonomous_run(...)` and appear in storage as an ordinary HCA run.
- Every autonomous run must carry `autonomy_agent_id`, `autonomy_trigger_id`, and `autonomy_mode` metadata on its `RunContext` and in its run record.
- A direct-execution path discovered in any autonomy route is a classification-changing failure, regardless of whether the outcome looks correct.

## Restart duplicate prevention

The supervisor must not relaunch a trigger that has already been accepted.

- Stop the backend process after `accept_trigger` succeeds but before the run reaches a terminal observation.
- Restart the process (`reset_supervisor()` plus fresh `AutonomySupervisor()` is equivalent in-process).
- On the next `tick()`, the supervisor must observe or resume the existing run. It must not launch a second run for the same `dedupe_key` or the same `(agent_id, trigger_id)` pair.
- Any second launch is a classification-changing failure.

## Artifact truth

If the evaluator, a proof step, or the report claims a run succeeded because an artifact should exist, that artifact must be verified present and linked.

- The file must exist on disk under the declared storage root.
- The file must be referenced from the run's event log or the corresponding storage index, not merely implied by a success event.
- An implied-but-missing artifact counts as a failed run even if all events look green.

## Rollback rule

If any release-seal edits to receipts, summaries, docs, or proof wiring cause:
- `./.venv/bin/python scripts/run_tests.py` to fail
or
- `./.venv/bin/python scripts/run_tests.py --autonomy` to fail
then:
1. revert the release-seal edits that introduced the regression
2. preserve the failing logs under `artifacts/proof/`
3. classify the result as `release not sealed`
4. report the exact file(s) whose release-seal changes caused the regression

Do not leave the repo in a state where the certification pass broke the certified build.

## Docs mismatch ledger

Every discrepancy between documentation and the fresh reality of this run must be recorded in this ledger so the final verdict is auditable rather than descriptive. Each row must be classified as either harmless drift or classification-changing drift; classification-changing drift blocks the hardened label.

| File | Claim | Reality | Classification |
| ---- | ----- | ------- | -------------- |
| *(none recorded yet)* | | | |
