## Runtime contracts

The runtime defines strict contracts for objects that circulate between components.  These contracts are implemented in `src/common/types.py` and used throughout the codebase.

### RunContext

Represents metadata about a run: a unique identifier, user ID, goal description, constraints, policy and safety profiles, timestamps and current environment.

### WorkspaceItem

Represents a unit of active information in the global workspace.  Each item carries its source module, content, salience and confidence scores, an uncertainty estimate, utility estimate, conflict references and provenance.  The runtime assigns an admission timestamp when the item enters the workspace.

### ModuleProposal

Modules communicate proposals in this form.  A proposal bundles a list of candidate `WorkspaceItem` instances, a rationale and metadata about confidence and novelty.  Proposals may depend on existing workspace items.

### ActionCandidate

When the runtime is ready to act, it creates a set of action candidates.  Each candidate describes the kind of action, its target and arguments, along with expected progress, uncertainty reduction, reversibility, risk, cost, interruption burden and policy alignment.  It also indicates whether an approval is required.

### MetaAssessment

The meta monitor returns an assessment summarising current confidence, flags for contradictions and missing information, an estimate of self limitations and a recommended runtime transition.  It also provides a brief explanation.

### MemoryRecord

Memory records store persistent information with a type (episodic, semantic, procedural or identity), subject, content, provenance, confidence, staleness and contradiction status.  They include a retention policy and timestamps.

### ExecutionReceipt

After an action is executed, the executor returns a receipt containing the action ID, status, timestamps, outputs, side effects, artifact references, any error and a hash for auditing.

### ApprovalRequest and ApprovalGrant

High‑risk actions generate an `ApprovalRequest` which is stored until a decision is made.  An `ApprovalGrant` attaches a token to the approved request.  The runtime must supply a valid token to resume execution.
