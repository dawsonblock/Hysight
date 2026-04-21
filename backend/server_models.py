import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class BackendModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class APIRootResponse(BackendModel):
    message: str


class StatusCheck(BackendModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class StatusCheckCreate(BackendModel):
    client_name: str


class DatabaseSubsystemStatus(BackendModel):
    enabled: bool
    status: str
    detail: str
    mongo_status_mode: str
    mongo_scope: str


class MemorySubsystemStatus(BackendModel):
    backend: str
    uses_sidecar: bool
    status: str
    detail: str
    memory_backend_mode: str
    service_available: Optional[bool] = None
    service_url: Optional[str] = None


class StorageSubsystemStatus(BackendModel):
    status: str
    detail: str
    root: str
    memory_dir: str


class LLMSubsystemStatus(BackendModel):
    status: str
    detail: str


class SubsystemsResponse(BackendModel):
    status: str
    consistency_check_passed: bool
    replay_authority: str
    hca_runtime_authority: str
    database: DatabaseSubsystemStatus
    memory: MemorySubsystemStatus
    storage: StorageSubsystemStatus
    llm: LLMSubsystemStatus
    autonomy: "AutonomySubsystemStatus"


class AutonomySubsystemStatus(BackendModel):
    enabled: bool
    running: bool
    active_agents: int
    active_runs: int
    pending_triggers: int
    pending_escalations: int = 0
    loop_running: bool = False
    kill_switch_active: bool = False
    kill_switch_reason: Optional[str] = None
    kill_switch_set_at: Optional[datetime] = None
    last_tick_at: Optional[datetime] = None
    last_error: Optional[str] = None
    last_evaluator_decision: Optional[str] = None
    current_attention_mode: Optional[str] = None
    interrupt_queue_length: int = 0
    reanchor_due: bool = False
    novelty_budget_remaining: Optional[int] = None
    hyperfocus_steps_used: int = 0
    last_reanchor_summary: Optional[Dict[str, Any]] = None
    dedupe_keys_tracked: int = 0
    recent_runs: List["AutonomyRunLinkResponse"] = Field(default_factory=list)
    budget_ledgers: List["AutonomyBudgetLedgerResponse"] = Field(default_factory=list)
    last_checkpoint: Optional["AutonomyCheckpointResponse"] = None


class AutonomyBudgetModel(BackendModel):
    max_steps_per_run: int = 50
    max_runs_per_agent: int = 25
    max_parallel_runs: int = 1
    max_retries_per_step: int = 2
    max_run_duration_seconds: int = 900
    deadman_timeout_seconds: int = 1800


class AutonomyPolicyModel(BackendModel):
    mode: str = "bounded"
    enabled: bool = True
    budget: AutonomyBudgetModel = Field(default_factory=AutonomyBudgetModel)
    approval_required_action_classes: List[str] = Field(default_factory=list)
    allowed_tool_names: List[str] = Field(default_factory=list)
    allowed_network_domains: List[str] = Field(default_factory=list)
    allowed_workspace_roots: List[str] = Field(default_factory=list)
    allow_memory_writes: bool = True
    allow_external_writes: bool = False
    auto_resume_after_approval: bool = False


class CreateAutonomyAgentRequest(BackendModel):
    name: str
    description: Optional[str] = None
    mode: str = "bounded"
    style_profile_id: str = "conservative_operator"
    policy: Optional[AutonomyPolicyModel] = None


class AutonomyAgentResponse(BackendModel):
    agent_id: str
    name: str
    description: Optional[str] = None
    mode: str
    status: str
    style_profile_id: str = "conservative_operator"
    policy: AutonomyPolicyModel
    created_at: datetime
    updated_at: datetime


class AutonomyAgentListResponse(BackendModel):
    agents: List[AutonomyAgentResponse] = Field(default_factory=list)


class CreateAutonomyScheduleRequest(BackendModel):
    agent_id: str
    interval_seconds: int
    goal_override: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class AutonomyScheduleResponse(BackendModel):
    schedule_id: str
    agent_id: str
    interval_seconds: int
    goal_override: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)
    enabled: bool
    last_fired_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class AutonomyScheduleListResponse(BackendModel):
    schedules: List[AutonomyScheduleResponse] = Field(default_factory=list)


class CreateAutonomyInboxItemRequest(BackendModel):
    agent_id: str
    goal: str
    payload: Dict[str, Any] = Field(default_factory=dict)


class AutonomyInboxItemResponse(BackendModel):
    item_id: str
    agent_id: str
    goal: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    status: str
    created_at: datetime
    claimed_at: Optional[datetime] = None


class AutonomyInboxListResponse(BackendModel):
    items: List[AutonomyInboxItemResponse] = Field(default_factory=list)


class AutonomyCheckpointResponse(BackendModel):
    agent_id: str
    trigger_id: str
    run_id: Optional[str] = None
    status: str
    attempt: int
    last_event_id: Optional[str] = None
    last_state: Optional[str] = None
    last_decision: Optional[str] = None
    resume_allowed: bool
    safe_to_continue: bool = True
    kill_switch_observed: bool = False
    idempotency: Optional[str] = None
    dedupe_key: Optional[str] = None
    style_profile_id: str = "conservative_operator"
    current_attention_mode: Optional[str] = None
    current_subgoal: Optional[str] = None
    interrupt_queue_length: int = 0
    reanchor_due: bool = False
    novelty_budget_remaining: Optional[int] = None
    hyperfocus_steps_used: int = 0
    last_reanchor_summary: Optional[Dict[str, Any]] = None
    checkpointed_at: datetime
    budget_snapshot: Dict[str, Any] = Field(default_factory=dict)


class AutonomyCheckpointListResponse(BackendModel):
    checkpoints: List[AutonomyCheckpointResponse] = Field(default_factory=list)


class AutonomyRunLinkResponse(BackendModel):
    agent_id: str
    trigger_id: str
    run_id: str
    run_status: str = ""
    last_state: Optional[str] = None
    last_decision: Optional[str] = None


class AutonomyRunListResponse(BackendModel):
    runs: List[AutonomyRunLinkResponse] = Field(default_factory=list)


class AutonomyStatusResponse(BackendModel):
    enabled: bool
    running: bool
    active_agents: int
    active_runs: int
    pending_triggers: int
    pending_escalations: int = 0
    loop_running: bool = False
    kill_switch_active: bool = False
    kill_switch_reason: Optional[str] = None
    kill_switch_set_at: Optional[datetime] = None
    last_tick_at: Optional[datetime] = None
    last_error: Optional[str] = None
    last_evaluator_decision: Optional[str] = None
    current_attention_mode: Optional[str] = None
    interrupt_queue_length: int = 0
    reanchor_due: bool = False
    novelty_budget_remaining: Optional[int] = None
    hyperfocus_steps_used: int = 0
    last_reanchor_summary: Optional[Dict[str, Any]] = None
    dedupe_keys_tracked: int = 0
    recent_runs: List["AutonomyRunLinkResponse"] = Field(default_factory=list)
    budget_ledgers: List["AutonomyBudgetLedgerResponse"] = Field(default_factory=list)
    last_checkpoint: Optional["AutonomyCheckpointResponse"] = None


class AutonomyControlResponse(BackendModel):
    agent_id: str
    status: str


class SetKillSwitchRequest(BackendModel):
    active: bool
    reason: Optional[str] = None
    set_by: Optional[str] = None


class AutonomyKillSwitchResponse(BackendModel):
    active: bool
    reason: Optional[str] = None
    set_at: Optional[datetime] = None
    cleared_at: Optional[datetime] = None
    set_by: Optional[str] = None


class AutonomyBudgetLedgerResponse(BackendModel):
    agent_id: str
    launched_runs_total: int = 0
    active_runs: int = 0
    total_steps_observed: int = 0
    total_retries_used: int = 0
    last_run_started_at: Optional[datetime] = None
    last_run_completed_at: Optional[datetime] = None
    last_budget_breach_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class AutonomyBudgetLedgerListResponse(BackendModel):
    ledgers: List[AutonomyBudgetLedgerResponse] = Field(default_factory=list)


class AutonomyEscalationResponse(BackendModel):
    agent_id: str
    trigger_id: str
    run_id: Optional[str] = None
    status: str
    last_state: Optional[str] = None
    last_decision: Optional[str] = None
    checkpointed_at: datetime


class AutonomyEscalationListResponse(BackendModel):
    escalations: List[AutonomyEscalationResponse] = Field(default_factory=list)


class AutonomyWorkspaceSnapshot(BackendModel):
    snapshot_at: datetime
    status: Optional[AutonomyStatusResponse] = None
    agents: List[AutonomyAgentResponse] = Field(default_factory=list)
    schedules: List[AutonomyScheduleResponse] = Field(default_factory=list)
    inbox: List[AutonomyInboxItemResponse] = Field(default_factory=list)
    runs: List[AutonomyRunLinkResponse] = Field(default_factory=list)
    escalations: List[AutonomyEscalationResponse] = Field(default_factory=list)
    budgets: List[AutonomyBudgetLedgerResponse] = Field(default_factory=list)
    checkpoints: List[AutonomyCheckpointResponse] = Field(default_factory=list)
    section_errors: Dict[str, str] = Field(default_factory=dict)


AutonomyStatusResponse.model_rebuild()
AutonomySubsystemStatus.model_rebuild()
SubsystemsResponse.model_rebuild()
AutonomyWorkspaceSnapshot.model_rebuild()