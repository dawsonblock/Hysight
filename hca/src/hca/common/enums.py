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
    memory_retrieved = "memory_retrieved"
    contradiction_detected = "contradiction_detected"
    snapshot_written = "snapshot_written"
    report_emitted = "report_emitted"
    run_failed = "run_failed"
    run_completed = "run_completed"


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