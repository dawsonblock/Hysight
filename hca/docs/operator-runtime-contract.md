# Operator Runtime Contract

This document freezes the current bounded Hysight contract from code reality. It is not aspirational. The authoritative implementation lives in the runtime, executor, registry, sandbox, replay, snapshot, approval, artifact, and memory code paths under `hca/src/hca`.

## Authority path

One side-effect path exists.

1. `Runtime` selects one canonical action or one workflow step at a time in `hca/src/hca/runtime/runtime.py`.
2. `build_action_candidate()` and `canonicalize_action_candidate()` in `hca/src/hca/executor/tool_registry.py` validate arguments and attach canonical binding and policy fingerprints.
3. `Executor.execute()` in `hca/src/hca/executor/executor.py` is the sole side-effect gateway.
4. Tool functions registered in `hca/src/hca/executor/tool_registry.py` perform bounded reads, bounded artifact writes, bounded repo mutation, or bounded allowlisted command execution.
5. Receipts, events, artifacts, approvals, and snapshots are appended to storage and replayed through the same contract.

No module is allowed to perform critical side effects outside executor-dispatched tools.

## Registry and tool rules

The tool registry is the source of truth for tool behavior. Each tool in `hca/src/hca/executor/tool_registry.py` defines:

- a typed input model
- canonical argument normalization
- action class and approval requirement
- timeout and bounded path scope metadata
- expected progress, uncertainty reduction, risk, cost, and interruption burden
- artifact behavior and side-effect class
- command allowlist metadata where relevant

The current bounded operator surface includes repo inspection tools, evidence/report tools, approval-bound mutation, run-scoped note or artifact persistence, and one bounded command tool.

## Canonical action identity

Canonical approved action identity is `ActionBinding`.

An action binding includes:

- tool name
- canonical target and normalized arguments
- action class and approval requirement
- policy snapshot and policy fingerprint
- action fingerprint

Approvals, receipts, snapshots, and replay all rely on the same canonical binding. Resume must re-canonicalize the selected action and match the original approval binding before execution.

## Approval semantics

Approval remains action-bound, not workflow-bound.

- High-risk tools request approval before execution.
- Grants are recorded separately from requests and consumption.
- Resume must present a matching approval id and token.
- Approval consumption only occurs after the canonical selected action still matches the approved binding.

Within a workflow, approval applies to the gated step only.

## Workflow semantics

The runtime supports bounded template-driven workflows selected through the same planning and executor path. Current workflow classes are:

- `investigation`
- `contract_api_drift`
- `targeted_mutation`
- `mutation_with_verification`
- `report_generation`

Workflow state persisted in run context, snapshots, and replay includes:

- `active_workflow`
- `workflow_budget`
- `workflow_checkpoint`
- `workflow_step_history`
- `workflow_artifacts`

The runtime still executes one validated step at a time. There is no open-ended autonomous loop.

`contract_api_drift` is no longer a relabeled investigation chain. It now performs bounded target-local search and read steps, then contrasts those results against a broader bounded contract surface before materializing a dedicated `contract_drift_summary` artifact and the final run report.

Workflow budgets are explicit and fail closed. If a workflow's configured budget is exhausted before the next declared step can run, the runtime emits `workflow_budget_exhausted` and terminates the run with a failed state rather than silently skipping steps.

If the next workflow step cannot be rebuilt from prior step outputs, the runtime emits `workflow_terminated` with reason `next_step_unbuildable` and fails the run rather than improvising arguments.

## Mutation guarantees

`patch_text_file` is the authoritative repo-mutation path.

Current guarantees:

- repo-root bounded path resolution
- text-file-only mutation
- bounded target size
- exact single-match replacement only
- preview and apply modes are explicit
- apply requires `expected_hash`
- before and after hashes are recorded
- unified diff artifact is always written
- successful apply marks touched paths and side effects
- writes are atomic through temp-file + `fsync` + `os.replace`
- no-op mutation requests fail closed

`replace_in_file` is currently a legacy alias to the same implementation.

## Command execution boundaries

`run_command` remains bounded and registry-governed.

Current guarantees in `hca/src/hca/executor/sandbox.py`:

- argv-only subprocess execution
- no shell-string execution
- no shell interpolation
- allowlisted executables and subcommands only
- repo-root bounded cwd
- controlled environment inheritance
- timeout enforcement with process-group termination
- deterministic stdout or stderr truncation
- exit-code capture
- explicit rejection of disallowed shell metacharacters in argv
- explicit rejection of dangerous flags that can redirect config, output, cwd, or manifest scope
- explicit rejection of repo-path escape through command arguments

The command surface is intentionally narrow and exists primarily for bounded verification.

## Artifact guarantees

Artifacts are first-class records, not ad hoc blobs.

Current typed artifact categories include:

- `investigation_summary`
- `patch_diff`
- `diff_report`
- `run_report`
- `command_result`

Artifact records and summaries capture run id, source action ids, file-path associations, hashes where available, approval linkage, workflow linkage, and storage path.

## Memory guarantees

Local episodic memory writes are authoritative for runtime completion. External memory ingestion is best-effort.

Current explicit outcomes emitted through events and surfaced in replay are:

- `episodic_memory_written`
- `external_memory_written`
- `external_memory_write_failed`

Those event payloads carry stable operator-facing fields including run id, sink, status, failure class, action id, action kind, workflow context, and finalization context.

External-memory failure is visible and non-silent, but it does not currently fail an otherwise successful run.

## Replay and snapshot guarantees

Replay reconstructs state from events, receipts, approvals, artifacts, and snapshots. It validates canonical action identity and surfaces discrepancies when the stored selected action, approval binding, or receipt lineage no longer agree.

Workflow-aware replay persists step history and workflow artifacts so consumers do not have to infer multi-step runs heuristically.

## Public run summary contract

The canonical operator-facing replay surface is `GET /api/hca/run/{run_id}` and the bounded list view `GET /api/hca/runs`.

That public contract is defined by `hca/src/hca/api/models.py` and populated by `hca/src/hca/api/run_views.py`. It is intentionally normalized and stricter than the raw trace.

Current structured summary sections include:

- `plan` for planner strategy, selected action, confidence, and planner fallback or memory-retrieval evidence
- `perception` for the interpreted intent class, intent label, and perception fallback metadata
- `critique` for the critic verdict, scores (`alignment`, `feasibility`, `safety`), issues, confidence delta, and critic fallback metadata
- `workflow_outcome` for structured workflow terminal state lifted from replayed events, including the terminal event and fail-closed reason when applicable
- `action_taken` and `action_result` for the canonical selected action and terminal receipt summary
- `memory_hits`, `memory_outcomes`, `workflow_*`, `discrepancies`, `key_events`, and `metrics` for replay-backed operator evidence

Consumers should treat that summary as the public contract and should not re-parse module-specific raw payloads from the event stream for fields that already appear there.

`GET /api/hca/run/{run_id}/events` remains the raw forensic surface. It is the correct place for full per-event payloads, candidate-item details, revision payloads, and other trace-level details that are intentionally not frozen into the normalized summary.

## Known intentional limits

The runtime is bounded and operator-oriented. It intentionally does not provide:

- arbitrary plugins
- unrestricted shell execution
- open-ended autonomous task loops
- workflow-level blanket approvals
- silent mutation or command failures
- production-grade claims without release evidence
