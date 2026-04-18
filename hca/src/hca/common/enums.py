"""Enumerations used throughout the hybrid cognitive agent."""

from enum import Enum


class RuntimeState(str, Enum):
    created = "created"
    initializing = "initializing"
    gathering_inputs = "gathering_inputs"
    proposing = "proposing"
    admitting = "admitting"
    broadcasting = "broadcasting"
    recurrent_update = "recurrent_update"
    action_selection = "action_selection"
    awaiting_approval = "awaiting_approval"
    executing = "executing"
    observing = "observing"
    memory_commit = "memory_commit"
    reporting = "reporting"
    completed = "completed"
    failed = "failed"
    halted = "halted"


class EventType(str, Enum):
    run_created = "run_created"
    state_transition = "state_transition"
    input_observed = "input_observed"
    module_proposed = "module_proposed"
    workspace_admitted = "workspace_admitted"
    workspace_rejected = "workspace_rejected"
    workspace_evicted = "workspace_evicted"
    broadcast_sent = "broadcast_sent"
    recurrent_pass_completed = "recurrent_pass_completed"
    meta_assessed = "meta_assessed"
    action_scored = "action_scored"
    action_selected = "action_selected"
    approval_requested = "approval_requested"
    approval_granted = "approval_granted"
    approval_denied = "approval_denied"
    execution_started = "execution_started"
    execution_finished = "execution_finished"
    observation_recorded = "observation_recorded"
    memory_written = "memory_written"
    episodic_memory_written = "episodic_memory_written"
    external_memory_written = "external_memory_written"
    external_memory_write_failed = "external_memory_write_failed"
    memory_retrieved = "memory_retrieved"
    contradiction_detected = "contradiction_detected"
    snapshot_written = "snapshot_written"
    report_emitted = "report_emitted"
    run_failed = "run_failed"
    run_completed = "run_completed"
    workflow_selected = "workflow_selected"
    workflow_step_started = "workflow_step_started"
    workflow_step_finished = "workflow_step_finished"
    workflow_budget_exhausted = "workflow_budget_exhausted"
    workflow_terminated = "workflow_terminated"
    autonomy_trigger_received = "autonomy_trigger_received"
    autonomy_trigger_accepted = "autonomy_trigger_accepted"
    autonomy_trigger_rejected = "autonomy_trigger_rejected"
    autonomy_run_launched = "autonomy_run_launched"
    autonomy_run_observed = "autonomy_run_observed"
    autonomy_checkpoint_written = "autonomy_checkpoint_written"
    autonomy_retry_scheduled = "autonomy_retry_scheduled"
    autonomy_escalation_requested = "autonomy_escalation_requested"
    autonomy_budget_exceeded = "autonomy_budget_exceeded"
    autonomy_stopped = "autonomy_stopped"


class AutonomyMode(str, Enum):
    manual = "manual"
    bounded = "bounded"
    supervised = "supervised"


class TriggerType(str, Enum):
    schedule = "schedule"
    inbox = "inbox"
    run_state_change = "run_state_change"
    memory_maintenance = "memory_maintenance"


class TriggerStatus(str, Enum):
    pending = "pending"
    accepted = "accepted"
    rejected = "rejected"
    completed = "completed"
    failed = "failed"


class InboxStatus(str, Enum):
    pending = "pending"
    claimed = "claimed"
    cancelled = "cancelled"
    completed = "completed"


class AgentStatus(str, Enum):
    active = "active"
    paused = "paused"
    stopped = "stopped"


class CheckpointStatus(str, Enum):
    launched = "launched"
    observing = "observing"
    awaiting_approval = "awaiting_approval"
    completed = "completed"
    failed = "failed"
    stopped = "stopped"
    retry_scheduled = "retry_scheduled"


class MemoryType(str, Enum):
    episodic = "episodic"
    semantic = "semantic"
    procedural = "procedural"
    identity = "identity"


class ActionClass(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class ApprovalDecision(str, Enum):
    pending = "pending"
    granted = "granted"
    denied = "denied"


class ControlSignal(str, Enum):
    proceed = "proceed"
    ask_user = "ask_user"
    retrieve_more = "retrieve_more"
    replan = "replan"
    backtrack = "backtrack"
    require_approval = "require_approval"
    halt = "halt"


class ReceiptStatus(str, Enum):
    success = "success"
    failure = "failure"
    pending = "pending"


class WorkflowClass(str, Enum):
    investigation = "investigation"
    contract_api_drift = "contract_api_drift"
    targeted_mutation = "targeted_mutation"
    mutation_with_verification = "mutation_with_verification"
    report_generation = "report_generation"


class WorkflowStepStatus(str, Enum):
    pending = "pending"
    awaiting_approval = "awaiting_approval"
    completed = "completed"
    failed = "failed"
    skipped = "skipped"


class ArtifactType(str, Enum):
    generic_file = "generic_file"
    investigation_summary = "investigation_summary"
    patch_diff = "patch_diff"
    diff_report = "diff_report"
    run_report = "run_report"
    command_result = "command_result"
