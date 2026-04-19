"""Autonomy triggers, schedules, inbox items, and agent records."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from hca.common.enums import (
    AgentStatus,
    AutonomyMode,
    InboxStatus,
    TriggerStatus,
    TriggerType,
)
from hca.common.time import utc_now
from hca.autonomy.policy import AutonomyPolicy


class AutonomyAgent(BaseModel):
    agent_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: Optional[str] = None
    mode: AutonomyMode = AutonomyMode.bounded
    status: AgentStatus = AgentStatus.active
    policy: AutonomyPolicy = Field(default_factory=AutonomyPolicy)
    style_profile_id: str = "conservative_operator"
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class AutonomyTrigger(BaseModel):
    trigger_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str
    trigger_type: TriggerType
    goal: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    not_before: Optional[datetime] = None
    dedupe_key: Optional[str] = None
    status: TriggerStatus = TriggerStatus.pending


class AutonomySchedule(BaseModel):
    schedule_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str
    interval_seconds: int
    goal_override: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    last_fired_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class AutonomyInboxItem(BaseModel):
    item_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str
    goal: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    status: InboxStatus = InboxStatus.pending
    created_at: datetime = Field(default_factory=utc_now)
    claimed_at: Optional[datetime] = None
