"""Typed API contracts for the runtime surface."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CreateRunRequest(BaseModel):
    goal: str
    user_id: Optional[str] = None


class CreateRunResponse(BaseModel):
    run_id: str


class ApprovalGrantRequest(BaseModel):
    token: Optional[str] = None
    actor: Optional[str] = None
    expires_at: Optional[datetime] = None


class ApprovalDenyRequest(BaseModel):
    actor: Optional[str] = None
    reason: Optional[str] = None


class ApprovalActionResponse(BaseModel):
    run_id: str
    approval_id: str
    decision: str
    status: str
    resolved_status: str
    state: str
    reason: Optional[str] = None
    token: Optional[str] = None


class ApprovalDecisionRequest(BaseModel):
    decision: str
    token: Optional[str] = None
    actor: Optional[str] = None
    reason: Optional[str] = None
    expires_at: Optional[datetime] = None


class ApprovalSummaryItem(BaseModel):
    approval_id: str
    status: str
    expired: bool = False
    request: Optional[Dict[str, Any]] = None
    decision: Optional[Dict[str, Any]] = None
    grant: Optional[Dict[str, Any]] = None
    consumption: Optional[Dict[str, Any]] = None
    corruption_count: int = 0


class ApprovalListResponse(BaseModel):
    approvals: List[ApprovalSummaryItem] = Field(default_factory=list)


class ReplayResponse(BaseModel):
    run_id: str
    state: str
    transition_history: List[str] = Field(default_factory=list)
    selected_action: Optional[Dict[str, Any]] = None
    selected_action_kind: Optional[str] = None
    workspace_summary: Dict[str, Any] = Field(default_factory=dict)
    pending_approval_id: Optional[str] = None
    approval: Optional[Dict[str, Any]] = None
    last_approval_decision: Optional[str] = None
    latest_receipt: Optional[Dict[str, Any]] = None
    latest_receipt_id: Optional[str] = None
    artifacts: List[Dict[str, Any]] = Field(default_factory=list)
    artifacts_count: int = 0
    memory_counts: Dict[str, int] = Field(default_factory=dict)
    event_count: int = 0
    meta_signals_seen: List[str] = Field(default_factory=list)
    discrepancies: List[str] = Field(default_factory=list)


class MemoryResponse(BaseModel):
    run_id: str
    memory_type: str
    items: List[Dict[str, Any]] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str
