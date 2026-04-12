## Runtime contracts

The runtime defines strict contracts for objects that circulate between components.  These contracts are implemented in `src/common/types.py` and used throughout the codebase.

### RunContext

Represents metadata about a run: a unique identifier, user ID, goal description, constraints, policy and safety profiles, timestamps and current environment.

When a bounded workflow plan is active, the run context also persists:

- the selected `active_workflow`
- workflow budget and checkpoint state
- `workflow_step_history`
- `workflow_artifacts`

This state is written into snapshots and replay output so workflow runs can resume and audit deterministically.

### WorkspaceItem

Represents a unit of active information in the global workspace.  Each item carries its source module, content, salience and confidence scores, an uncertainty estimate, utility estimate, conflict references and provenance.  The runtime assigns an admission timestamp when the item enters the workspace.

### ModuleProposal

Modules communicate proposals in this form.  A proposal bundles a list of candidate `WorkspaceItem` instances, a rationale and metadata about confidence and novelty.  Proposals may depend on existing workspace items.

### ActionCandidate

When the runtime is ready to act, it creates a set of action candidates.  Each candidate describes the kind of action, its target and arguments, along with expected progress, uncertainty reduction, reversibility, risk, cost, interruption burden and policy alignment.  It also indicates whether an approval is required.

Workflow-backed candidates additionally carry the workflow identity and the current workflow step identity so the executor and replay layers can attribute receipts and approvals to the correct step.

### WorkflowPlan, WorkflowStep and WorkflowCheckpoint

`WorkflowPlan` describes a bounded template selected by the planner/runtime.  It contains:

- a workflow class and strategy identifier
- bounded workflow parameters derived from the user goal
- an ordered list of `WorkflowStep` definitions
- a maximum step budget and termination condition

Each `WorkflowStep` binds a registry tool name to an argument template.  Argument templates may refer to workflow parameters or prior step outputs, but they must still resolve into ordinary tool arguments before execution.

`contract_api_drift` is a dedicated bounded workflow family.  Its declared steps first inspect the target-local surface, then search and read a broader bounded contract surface, and finally emit a deterministic `contract_drift_summary` artifact before the terminal run report.

`WorkflowCheckpoint` captures where the runtime is within the selected workflow so pause/resume and replay can continue from the correct step without reconstructing side effects heuristically.

If the next step cannot be reconstructed from prior outputs, the runtime fails closed with `workflow_terminated` reason `next_step_unbuildable`.  If a configured workflow step budget is exhausted before the next declared step can run, the runtime emits `workflow_budget_exhausted` and terminates the run as failed.

### MetaAssessment

The meta monitor returns an assessment summarising current confidence, flags for contradictions and missing information, an estimate of self limitations and a recommended runtime transition.  It also provides a brief explanation.

### MemoryRecord

Memory records store persistent information with a type (episodic, semantic, procedural or identity), subject, content, provenance, confidence, staleness and contradiction status.  They include a retention policy and timestamps.

### ExecutionReceipt

After an action is executed, the executor returns a receipt containing the action ID, status, timestamps, outputs, side effects, artifact references, any error and a hash for auditing.

Workflow-aware receipts now also carry:

- `workflow_id` and `workflow_step_id`
- `touched_paths`
- typed `artifact_summaries`
- structured `mutation_result`

For workflow runs, the terminal `latest_receipt` in a snapshot may belong to `create_run_report` instead of the mutating or verification step.  Consumers that need mutation-specific evidence should inspect the relevant workflow step receipt or workflow history.

### ArtifactSummary and MutationResult

`ArtifactSummary` provides normalized artifact metadata for downstream reporting and replay.  It records the artifact type, path, hashes, file-path associations, approval provenance, and source action references.

`MutationResult` captures certified mutation details such as before/after hashes, changed lines, and other bounded patch metadata that must survive reporting and replay.

### ApprovalRequest and ApprovalGrant

High‑risk actions generate an `ApprovalRequest` which is stored until a decision is made.  An `ApprovalGrant` attaches a token to the approved request.  The runtime must supply a valid token to resume execution.

Within a workflow, approval still applies to the individual canonical action binding for the gated step.  Approval is not granted to the workflow as a whole.
