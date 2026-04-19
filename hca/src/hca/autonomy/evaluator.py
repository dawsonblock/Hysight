"""Post-step evaluator for bounded autonomy.

The evaluator consumes the current run state, the event log, the agent's
policy, the durable budget ledger, and the kill-switch record, and returns a
structured :class:`EvaluatorReport`. The supervisor never decides
``continue`` on its own — it asks the evaluator, then acts on the report.

This keeps continuation logic in one deterministic place instead of being
scattered through ``AutonomySupervisor``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from hca.autonomy.checkpoint import AutonomyBudgetLedger, AutonomyKillSwitch
from hca.autonomy.policy import AutonomyPolicy, PolicyDecision
from hca.common.enums import (
    EventType,
    EvaluatorDecision,
    Idempotency,
    RuntimeState,
)
from hca.common.time import utc_now
from hca.common.types import RunContext


@dataclass
class EvaluatorReport:
    """Structured evaluator output consumed by the supervisor."""

    decision: EvaluatorDecision
    reason: Optional[str] = None
    evidence: Dict[str, Any] = field(default_factory=dict)
    # Whether the most recent side-effecting action has known idempotency
    # semantics. ``unknown`` is treated as ``non_idempotent`` by gates.
    idempotency: Idempotency = Idempotency.unknown
    # Post-check guard: if False, the supervisor must not blindly retry.
    safe_to_continue: bool = True


_TERMINAL_STATES = {
    RuntimeState.completed,
    RuntimeState.failed,
    RuntimeState.halted,
}


def _count_step_events(events: List[Dict[str, Any]]) -> int:
    return sum(
        1
        for event in events
        if event.get("event_type")
        in {
            EventType.execution_started.value,
            EventType.workflow_step_started.value,
        }
    )


def _count_retry_events(events: List[Dict[str, Any]]) -> int:
    return sum(
        1
        for event in events
        if event.get("event_type")
        == EventType.autonomy_retry_scheduled.value
    )


def _last_action_class(events: List[Dict[str, Any]]) -> Optional[str]:
    for event in reversed(events):
        if event.get("event_type") == EventType.action_selected.value:
            payload = event.get("payload") or {}
            value = payload.get("action_class")
            if isinstance(value, str):
                return value
    return None


def _run_duration_seconds(context: RunContext) -> float:
    if context.created_at is None:
        return 0.0
    return max(0.0, (utc_now() - context.created_at).total_seconds())


def evaluate(
    *,
    context: RunContext,
    events: List[Dict[str, Any]],
    policy: AutonomyPolicy,
    ledger: AutonomyBudgetLedger,
    kill_switch: AutonomyKillSwitch,
    idempotency: Idempotency = Idempotency.unknown,
) -> EvaluatorReport:
    """Return a structured decision for the supervisor.

    Hard gates come first (kill switch > budget > deadman), then terminal
    state, then approval, then continuation.
    """

    # 1. Kill switch — hard stop.
    if kill_switch.active:
        return EvaluatorReport(
            decision=EvaluatorDecision.stop_killed,
            reason="kill_switch_active",
            evidence={"kill_switch_reason": kill_switch.reason},
            idempotency=idempotency,
            safe_to_continue=False,
        )

    # 2. Budget / deadman (per-run).
    step_events = _count_step_events(events)
    retry_events = _count_retry_events(events)
    budget_decision: PolicyDecision = policy.check_budget(
        runs_launched=0,
        parallel_runs=0,
        steps_in_current_run=step_events,
        retries_for_current_step=retry_events,
        run_duration_seconds=_run_duration_seconds(context),
    )
    if not budget_decision.allowed:
        if budget_decision.reason == "deadman_timeout_exceeded":
            return EvaluatorReport(
                decision=EvaluatorDecision.stop_deadman,
                reason=budget_decision.reason,
                evidence=budget_decision.evidence,
                idempotency=idempotency,
                safe_to_continue=False,
            )
        return EvaluatorReport(
            decision=EvaluatorDecision.stop_budget,
            reason=budget_decision.reason,
            evidence=budget_decision.evidence,
            idempotency=idempotency,
            safe_to_continue=False,
        )

    # 3. Terminal states.
    if context.state == RuntimeState.completed:
        return EvaluatorReport(
            decision=EvaluatorDecision.complete,
            reason="run_completed",
            evidence={"state": context.state.value},
            idempotency=idempotency,
        )
    if context.state in _TERMINAL_STATES and context.state != RuntimeState.completed:
        return EvaluatorReport(
            decision=EvaluatorDecision.retry,
            reason=f"run_state_{context.state.value}",
            evidence={"state": context.state.value},
            idempotency=idempotency,
            safe_to_continue=idempotency == Idempotency.idempotent,
        )

    # 4. Approval escalation.
    if context.state == RuntimeState.awaiting_approval:
        return EvaluatorReport(
            decision=EvaluatorDecision.escalate,
            reason="run_awaiting_approval",
            evidence={"pending_approval_id": context.pending_approval_id},
            idempotency=idempotency,
            safe_to_continue=False,
        )

    # 5. High-risk action without approval → escalate rather than continue.
    last_class = _last_action_class(events)
    if (
        last_class is not None
        and last_class in policy.approval_required_action_classes
    ):
        return EvaluatorReport(
            decision=EvaluatorDecision.escalate,
            reason="high_risk_action_requires_approval",
            evidence={"action_class": last_class},
            idempotency=idempotency,
            safe_to_continue=False,
        )

    # 6. Default — observe.
    return EvaluatorReport(
        decision=EvaluatorDecision.continue_observe,
        reason="within_budget",
        evidence={
            "steps": step_events,
            "retries": retry_events,
            "ledger_active_runs": ledger.active_runs,
        },
        idempotency=idempotency,
        safe_to_continue=idempotency != Idempotency.non_idempotent,
    )
