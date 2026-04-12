"""Typed API contracts for the runtime surface."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from hca.api.run_views import RunSummaryResponse


class APIModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


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
