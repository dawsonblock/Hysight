"""Canonical typed API contracts for the runtime surface."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class APIModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RunAPIModel(APIModel):
    pass


class RunPlanResponse(RunAPIModel):
    strategy: Optional[str] = None
    action: Optional[str] = None
    rationale: str = ""
    confidence: float = 1.0
    memory_context_used: bool = False
    planning_mode: Optional[str] = None
    fallback_reason: Optional[str] = None
    memory_retrieval_status: Optional[str] = None
    memory_retrieval_error: Optional[str] = None


class RunActionResponse(RunAPIModel):
    kind: Optional[str] = None
    arguments: Dict[str, Any] = Field(default_factory=dict)
    action_id: Optional[str] = None
    requires_approval: bool = False


class RunResultResponse(RunAPIModel):
    status: Optional[str] = None
    outputs: Optional[Dict[str, Any]] = None
    artifacts: List[str] = Field(default_factory=list)
    error: Optional[str] = None


class RunMemoryHitResponse(RunAPIModel):
    text: str
    score: float
    memory_type: Optional[str] = None
    stored_at: Optional[datetime] = None


class RunKeyEventResponse(RunAPIModel):
    type: str
    actor: Optional[str] = None
    timestamp: Optional[datetime] = None
    summary: str


class RunLatencySummaryResponse(RunAPIModel):
    count: int = 0
    total_ms: float = 0.0
    max_ms: float = 0.0
    last_ms: Optional[float] = None


class RunMetricsResponse(RunAPIModel):
    run_duration_ms: Optional[float] = None
    tool_latency: RunLatencySummaryResponse = Field(
        default_factory=RunLatencySummaryResponse
    )
    memory_retrieval_latency: RunLatencySummaryResponse = Field(
        default_factory=RunLatencySummaryResponse
    )
    memory_commit_latency: RunLatencySummaryResponse = Field(
        default_factory=RunLatencySummaryResponse
    )


class RunSummaryResponse(RunAPIModel):
    run_id: str
    goal: str
    state: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    plan: RunPlanResponse = Field(default_factory=RunPlanResponse)
    action_taken: RunActionResponse = Field(default_factory=RunActionResponse)
    action_result: RunResultResponse = Field(default_factory=RunResultResponse)
    approval_id: Optional[str] = None
    approval: Optional[Dict[str, Any]] = None
    last_approval_decision: Optional[str] = None
    latest_receipt: Optional[Dict[str, Any]] = None
    artifacts: List[Dict[str, Any]] = Field(default_factory=list)
    artifacts_count: int = 0
    memory_counts: Dict[str, int] = Field(default_factory=dict)
    memory_outcomes: Dict[str, Any] = Field(default_factory=dict)
    active_workflow: Optional[Dict[str, Any]] = None
    workflow_budget: Optional[Dict[str, Any]] = None
    workflow_checkpoint: Optional[Dict[str, Any]] = None
    workflow_step_history: List[Dict[str, Any]] = Field(default_factory=list)
    workflow_artifacts: List[Dict[str, Any]] = Field(default_factory=list)
    discrepancies: List[str] = Field(default_factory=list)
    memory_hits: List[RunMemoryHitResponse] = Field(default_factory=list)
    key_events: List[RunKeyEventResponse] = Field(default_factory=list)
    event_count: int = 0
    metrics: RunMetricsResponse = Field(default_factory=RunMetricsResponse)


class RunListResponse(RunAPIModel):
    records: List[RunSummaryResponse] = Field(default_factory=list)
    total: int = 0


class RunEventResponse(RunAPIModel):
    event_id: str
    run_id: str
    event_type: str
    actor: Optional[str] = None
    timestamp: Optional[datetime] = None
    summary: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    prior_state: Optional[str] = None
    next_state: Optional[str] = None
    is_key_event: bool = False


class RunEventListResponse(RunAPIModel):
    run_id: str
    records: List[RunEventResponse] = Field(default_factory=list)
    total: int = 0


class RunArtifactResponse(RunAPIModel):
    artifact_id: str
    run_id: str
    action_id: str
    kind: str
    path: str
    source_action_ids: List[str] = Field(default_factory=list)
    file_paths: List[str] = Field(default_factory=list)
    hashes: Dict[str, str] = Field(default_factory=dict)
    approval_id: Optional[str] = None
    workflow_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None
    content_available: bool = False


class RunArtifactListResponse(RunAPIModel):
    run_id: str
    records: List[RunArtifactResponse] = Field(default_factory=list)
    total: int = 0


class RunArtifactDetailResponse(RunArtifactResponse):
    content: Optional[str] = None
    size_bytes: int = 0
    truncated: bool = False


class CreateRunRequest(APIModel):
    goal: str
    user_id: Optional[str] = None


class CreateRunResponse(APIModel):
    run_id: str


class ApprovalSelectionRequest(APIModel):
    approval_id: str


class ApprovalGrantRequest(APIModel):
    token: Optional[str] = None
    actor: Optional[str] = None
    expires_at: Optional[datetime] = None


class ApprovalDenyRequest(APIModel):
    actor: Optional[str] = None
    reason: Optional[str] = None


class ApprovalActionResponse(APIModel):
    run_id: str
    approval_id: str
    decision: str
    status: str
    resolved_status: str
    state: str
    reason: Optional[str] = None
    token: Optional[str] = None


class ApprovalDecisionRequest(APIModel):
    decision: str
    token: Optional[str] = None
    actor: Optional[str] = None
    reason: Optional[str] = None
    expires_at: Optional[datetime] = None


class ApprovalSummaryItem(APIModel):
    approval_id: str
    status: str
    expired: bool = False
    request: Optional[Dict[str, Any]] = None
    decision: Optional[Dict[str, Any]] = None
    grant: Optional[Dict[str, Any]] = None
    consumption: Optional[Dict[str, Any]] = None
    corruption_count: int = 0


class ApprovalListResponse(APIModel):
    approvals: List[ApprovalSummaryItem] = Field(default_factory=list)


class ReplayResponse(RunSummaryResponse):
    """Compatibility alias for the shared replay-backed run summary."""


class MemoryResponse(APIModel):
    run_id: str
    memory_type: str
    items: List[Dict[str, Any]] = Field(default_factory=list)


class HealthResponse(APIModel):
    status: str
