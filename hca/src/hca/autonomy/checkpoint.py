"""Autonomy checkpoint and run-link records."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from hca.common.enums import CheckpointStatus
from hca.common.time import utc_now


class AutonomyBudgetState(BaseModel):
    runs_launched: int = 0
    parallel_runs: int = 0
    steps_in_current_run: int = 0
    retries_for_current_step: int = 0
    run_started_at: Optional[datetime] = None


class AutonomyRunLink(BaseModel):
    agent_id: str
    trigger_id: str
    run_id: str


class AutonomyCheckpoint(BaseModel):
    agent_id: str
    trigger_id: str
    run_id: Optional[str] = None
    status: CheckpointStatus = CheckpointStatus.launched
    attempt: int = 0
    last_event_id: Optional[str] = None
    last_state: Optional[str] = None
    last_decision: Optional[str] = None
    resume_allowed: bool = False
    checkpointed_at: datetime = Field(default_factory=utc_now)
    budget_snapshot: Dict[str, Any] = Field(default_factory=dict)
