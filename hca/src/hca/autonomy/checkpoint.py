"""Autonomy checkpoint and run-link records."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from hca.common.enums import CheckpointStatus, Idempotency
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
    # Set at checkpoint time. False means continuation after restart is not
    # safe without operator review (e.g. non-idempotent side-effect
    # in-flight, kill switch active at last observation).
    safe_to_continue: bool = True
    # Kill-switch state observed at checkpoint time. Persisted so a restart
    # can see the supervisor's prior view without reloading global state.
    kill_switch_observed: bool = False
    # Idempotency hint of the most recent side-effecting action, when known.
    idempotency: Idempotency = Idempotency.unknown
    # Persisted dedupe key for the trigger that produced this checkpoint.
    # None for historical records.
    dedupe_key: Optional[str] = None
    style_profile_id: str = "conservative_operator"
    current_attention_mode: str = "stable"
    current_subgoal: Optional[str] = None
    queued_interrupts: list[Dict[str, Any]] = Field(default_factory=list)
    queued_branches: list[Dict[str, Any]] = Field(default_factory=list)
    reanchor_due_at_step: int = 0
    hyperfocus_steps_used: int = 0
    novelty_budget_used: int = 0
    last_reanchor_summary: Optional[Dict[str, Any]] = None
    checkpointed_at: datetime = Field(default_factory=utc_now)
    budget_snapshot: Dict[str, Any] = Field(default_factory=dict)


class AutonomyBudgetLedger(BaseModel):
    """Durable per-agent budget ledger.

    Reloaded on supervisor restart so budgets never rely on in-memory
    counters. Append-only updates; latest record wins.
    """

    agent_id: str
    launched_runs_total: int = 0
    active_runs: int = 0
    total_steps_observed: int = 0
    total_retries_used: int = 0
    last_run_started_at: Optional[datetime] = None
    last_run_completed_at: Optional[datetime] = None
    last_budget_breach_at: Optional[datetime] = None
    updated_at: datetime = Field(default_factory=utc_now)


class AutonomyKillSwitch(BaseModel):
    """Durable global autonomy kill switch.

    When ``active`` is true:
    - ``accept_trigger`` rejects all new triggers with ``kill_switch_active``.
    - ``observe_run`` stops continuation of existing autonomous runs.
    - Manual HCA runs are unaffected (supervisor never touches them).
    """

    active: bool = False
    reason: Optional[str] = None
    set_at: Optional[datetime] = None
    cleared_at: Optional[datetime] = None
    set_by: Optional[str] = None
