"""Common data types and models for the HCA."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any, Dict, List, Optional

from pydantic import AfterValidator, BaseModel, Field, field_validator

from hca.common.enums import (
    RuntimeState,
    MemoryType,
    ActionClass,
    ApprovalDecision,
    ControlSignal,
    ReceiptStatus,
)
from hca.common.time import ensure_utc, utc_now


UtcDateTime = Annotated[datetime, AfterValidator(ensure_utc)]


class RunContext(BaseModel):
    run_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: Optional[str] = None
    goal: str
    constraints: Optional[str] = None
    active_environment: Optional[str] = None
    policy_profile: Optional[str] = None
    safety_profile: Optional[str] = None
    created_at: UtcDateTime = Field(default_factory=utc_now)
    updated_at: UtcDateTime = Field(default_factory=utc_now)
    # Runtime state tracking
    state: RuntimeState = RuntimeState.created
    replan_budget: int = 3
    current_replan_count: int = 0
    pending_approval_id: Optional[str] = None


class WorkspaceItem(BaseModel):
    item_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_module: str
    kind: str
    content: Any
    salience: float = 0.0
    confidence: float = 1.0
    score: float = 0.0
    uncertainty: float = 0.0
    utility_estimate: float = 0.0
    conflict_refs: List[str] = Field(default_factory=list)
    provenance: List[str] = Field(default_factory=list)
    admitted_at: Optional[UtcDateTime] = None
    admission_reason: Optional[str] = None
    # Metadata for meta-control
    contradiction_status: bool = False
    staleness: float = 0.0


class ModuleProposal(BaseModel):
    proposal_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_module: str
    candidate_items: List[WorkspaceItem]
    rationale: Optional[str] = None
    depends_on: List[str] = Field(default_factory=list)
    confidence: float = 1.0
    novelty_score: float = 0.0
    estimated_value: float = 0.0


class ActionCandidate(BaseModel):
    action_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    kind: str
    target: Optional[str] = None
    arguments: Dict[str, Any] = Field(default_factory=dict)
    expected_progress: float = 0.0
    expected_uncertainty_reduction: float = 0.0
    reversibility: float = 1.0
    risk: float = 0.0
    cost: float = 0.0
    user_interruption_burden: float = 0.0
    policy_alignment: float = 1.0
    requires_approval: bool = False
    provenance: List[str] = Field(default_factory=list)


class MetaAssessment(BaseModel):
    assessment_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    overall_confidence: float
    contradiction_flags: List[str] = Field(default_factory=list)
    missing_information: List[str] = Field(default_factory=list)
    self_limitations: List[str] = Field(default_factory=list)
    recommended_transition: ControlSignal
    reason_code: Optional[str] = None
    explanation: Optional[str] = None


class MemoryRecord(BaseModel):
    record_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    memory_type: MemoryType
    run_id: Optional[str] = None  # Added run_id for store compatibility
    subject: Optional[str] = None
    content: Any
    source_run: Optional[str] = None
    provenance: List[str] = Field(default_factory=list)
    confidence: float = 1.0
    staleness: float = 0.0
    contradiction_status: bool = False
    retention_policy: Optional[str] = None
    created_at: UtcDateTime = Field(default_factory=utc_now)
    updated_at: UtcDateTime = Field(default_factory=utc_now)


class RetrievalItem(BaseModel):
    record: MemoryRecord
    confidence: float
    staleness: float
    contradiction: bool = False
    provenance: List[str] = Field(default_factory=list)
    memory_type: MemoryType


class ContradictionResult(BaseModel):
    has_contradiction: bool
    reason: Optional[str] = None
    subject: Optional[str] = None
    conflicting_record_ids: List[str] = Field(default_factory=list)


class PromotionCandidate(BaseModel):
    candidate_type: MemoryType
    subject: Optional[str] = None
    content: Any = None
    supporting_record_ids: List[str] = Field(default_factory=list)
    confidence: float = 0.0
    support_count: int = 0
    contradiction_free: bool = True


class ConflictRecord(BaseModel):
    item_ids: List[str] = Field(default_factory=list)
    reason_code: str
    details: Dict[str, Any] = Field(default_factory=dict)


class MissingInfoResult(BaseModel):
    item_id: str
    action_kind: str
    missing_fields: List[str] = Field(default_factory=list)


class CapabilitySummary(BaseModel):
    available_tools: List[str] = Field(default_factory=list)
    approval_gated_tools: List[str] = Field(default_factory=list)
    unsupported_requested_actions: List[str] = Field(default_factory=list)
    failure_count: int = 0


class ExecutionReceipt(BaseModel):
    receipt_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    action_id: str
    status: ReceiptStatus
    started_at: UtcDateTime = Field(default_factory=utc_now)
    finished_at: Optional[UtcDateTime] = None
    outputs: Optional[Any] = None
    side_effects: Optional[List[str]] = None
    artifacts: Optional[List[str]] = None
    error: Optional[str] = None
    audit_hash: Optional[str] = None


class ApprovalRequest(BaseModel):
    approval_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    run_id: str
    action_id: str
    action_class: ActionClass
    reason: str
    requested_at: UtcDateTime = Field(default_factory=utc_now)
    expires_at: Optional[UtcDateTime] = None


class ApprovalDecisionRecord(BaseModel):
    approval_id: str
    decision: ApprovalDecision
    actor: str = "user"
    reason: Optional[str] = None
    decided_at: UtcDateTime = Field(default_factory=utc_now)
    expires_at: Optional[UtcDateTime] = None

    @field_validator("decision")
    @classmethod
    def _validate_terminal_decision(
        cls, value: ApprovalDecision
    ) -> ApprovalDecision:
        if value == ApprovalDecision.pending:
            raise ValueError(
                "ApprovalDecisionRecord must be granted or denied"
            )
        return value


class ApprovalGrant(BaseModel):
    approval_id: str
    token: str
    actor: str = "user"
    granted_at: UtcDateTime = Field(default_factory=utc_now)
    expires_at: Optional[UtcDateTime] = None


class ApprovalConsumption(BaseModel):
    approval_id: str
    token: str
    consumed_at: UtcDateTime = Field(default_factory=utc_now)


class ArtifactRecord(BaseModel):
    artifact_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    run_id: str
    action_id: str
    kind: str
    path: str
    metadata: Optional[Dict[str, Any]] = None
    created_at: UtcDateTime = Field(default_factory=utc_now)


class SnapshotRecord(BaseModel):
    snapshot_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    run_id: str
    state: RuntimeState
    workspace: List[WorkspaceItem]
    memory_summary: Dict[str, int] = Field(default_factory=dict)
    pending_approval: Optional[str] = None
    latest_receipt: Optional[str] = None
    created_at: UtcDateTime = Field(default_factory=utc_now)
    # Added for v5 compatibility
    timestamp: UtcDateTime = Field(default_factory=utc_now)
    workspace_summary: Dict[str, Any] = Field(default_factory=dict)
    pending_approval_id: Optional[str] = None
    selected_action: Optional[Dict[str, Any]] = None
