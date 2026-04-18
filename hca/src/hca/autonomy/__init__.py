"""Bounded operator-supervised autonomy layer on top of the HCA runtime.

This package never executes tools directly. Instead the supervisor converts
accepted inbox/schedule triggers into ordinary ``Runtime.run(...)`` invocations,
attaches autonomy metadata to the existing ``RunContext``, observes progress
through the replay/event log, and respects the existing approval/memory model.
"""

from __future__ import annotations

from hca.common.enums import (
    AgentStatus,
    AutonomyMode,
    CheckpointStatus,
    InboxStatus,
    TriggerStatus,
    TriggerType,
)

from hca.autonomy.policy import (
    AutonomyBudget,
    AutonomyPolicy,
    PolicyDecision,
)
from hca.autonomy.triggers import (
    AutonomyAgent,
    AutonomyInboxItem,
    AutonomySchedule,
    AutonomyTrigger,
)
from hca.autonomy.checkpoint import (
    AutonomyBudgetState,
    AutonomyCheckpoint,
    AutonomyRunLink,
)

__all__ = [
    "AgentStatus",
    "AutonomyAgent",
    "AutonomyBudget",
    "AutonomyBudgetState",
    "AutonomyCheckpoint",
    "AutonomyInboxItem",
    "AutonomyMode",
    "AutonomyPolicy",
    "AutonomyRunLink",
    "AutonomySchedule",
    "AutonomyTrigger",
    "CheckpointStatus",
    "InboxStatus",
    "PolicyDecision",
    "TriggerStatus",
    "TriggerType",
]
