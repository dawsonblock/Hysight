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

from hca.autonomy.attention_controller import AttentionController
from hca.autonomy.checkpoint import (
    AutonomyBudgetLedger,
    AutonomyCheckpoint,
    AutonomyKillSwitch,
)
from hca.autonomy.policy import AutonomyPolicy, PolicyDecision
from hca.autonomy.style_profile import AttentionMode, OperatorStyleProfile, get_style_profile
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


def _count_events(events: List[Dict[str, Any]], *event_types: str) -> int:
    targets = set(event_types)
    return sum(1 for event in events if event.get("event_type") in targets)


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


def _parse_attention_mode(
    checkpoint: Optional[AutonomyCheckpoint],
    style_profile: OperatorStyleProfile,
) -> AttentionMode:
    if checkpoint is None:
        return style_profile.default_attention_mode
    try:
        return AttentionMode(checkpoint.current_attention_mode)
    except ValueError:
        return style_profile.default_attention_mode


def _steps_since_reanchor(
    checkpoint: Optional[AutonomyCheckpoint],
    style_profile: OperatorStyleProfile,
    step_events: int,
) -> int:
    if checkpoint is None or checkpoint.reanchor_due_at_step <= 0:
        return step_events
    anchor = max(0, checkpoint.reanchor_due_at_step - style_profile.reanchor_interval_steps)
    return max(0, step_events - anchor)


def _drift_score(
    *,
    context: RunContext,
    events: List[Dict[str, Any]],
    checkpoint: Optional[AutonomyCheckpoint],
    style_profile: OperatorStyleProfile,
    step_events: int,
    retry_events: int,
) -> float:
    score = 0.0
    if context.state == RuntimeState.awaiting_approval:
        score += 0.20
    if retry_events:
        score += min(0.20, retry_events * 0.10)
    if _count_events(events, EventType.contradiction_detected.value):
        score += 0.15
    if checkpoint is not None and checkpoint.queued_interrupts:
        score += min(0.20, len(checkpoint.queued_interrupts) * 0.08)
    if checkpoint is not None and checkpoint.current_attention_mode == AttentionMode.exploratory.value:
        score += 0.08
    if step_events >= style_profile.reanchor_interval_steps:
        score += 0.25
    return min(1.0, score)


def _novelty_score(
    *,
    events: List[Dict[str, Any]],
    checkpoint: Optional[AutonomyCheckpoint],
    style_profile: OperatorStyleProfile,
) -> float:
    score = 0.10
    score += min(
        0.20,
        _count_events(
            events,
            EventType.input_observed.value,
            EventType.workspace_admitted.value,
            EventType.observation_recorded.value,
        )
        * 0.03,
    )
    if checkpoint is not None and checkpoint.queued_interrupts:
        score += min(0.25, len(checkpoint.queued_interrupts) * 0.10)
    score += style_profile.trait_weights.novelty_seeking * 0.15
    return min(1.0, score)


def _urgency_score(checkpoint: Optional[AutonomyCheckpoint]) -> float:
    if checkpoint is None or not checkpoint.queued_interrupts:
        return 0.0
    urgency_values = [
        float(item.get("urgency", 0.5) or 0.5)
        for item in checkpoint.queued_interrupts
        if isinstance(item, dict)
    ]
    if not urgency_values:
        return 0.0
    return max(0.0, min(1.0, max(urgency_values)))


def _return_on_focus_score(
    *,
    context: RunContext,
    checkpoint: Optional[AutonomyCheckpoint],
    style_profile: OperatorStyleProfile,
    step_events: int,
) -> float:
    score = 0.55
    if context.state in {RuntimeState.executing, RuntimeState.observing}:
        score += 0.15
    if step_events <= style_profile.hyperfocus_max_steps:
        score += 0.10
    if checkpoint is not None and checkpoint.current_attention_mode == AttentionMode.hyperfocus.value:
        score += 0.10
    return min(1.0, score)


def evaluate(
    *,
    context: RunContext,
    events: List[Dict[str, Any]],
    policy: AutonomyPolicy,
    ledger: AutonomyBudgetLedger,
    kill_switch: AutonomyKillSwitch,
    idempotency: Idempotency = Idempotency.unknown,
    checkpoint: Optional[AutonomyCheckpoint] = None,
    style_profile: Optional[OperatorStyleProfile] = None,
) -> EvaluatorReport:
    """Return a structured decision for the supervisor.

    Hard gates come first (kill switch > budget > deadman), then terminal
    state, then approval, then style-aware re-anchoring and continuation.
    """

    style_profile = style_profile or get_style_profile(
        getattr(context, "autonomy_style_profile_id", None)
    )

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
    if last_class is not None and last_class in policy.approval_required_action_classes:
        return EvaluatorReport(
            decision=EvaluatorDecision.escalate,
            reason="high_risk_action_requires_approval",
            evidence={"action_class": last_class},
            idempotency=idempotency,
            safe_to_continue=False,
        )

    current_mode = _parse_attention_mode(checkpoint, style_profile)
    steps_since_reanchor = _steps_since_reanchor(checkpoint, style_profile, step_events)
    drift_score = _drift_score(
        context=context,
        events=events,
        checkpoint=checkpoint,
        style_profile=style_profile,
        step_events=step_events,
        retry_events=retry_events,
    )
    novelty_score = _novelty_score(
        events=events,
        checkpoint=checkpoint,
        style_profile=style_profile,
    )
    urgency_score = _urgency_score(checkpoint)
    return_on_focus_score = _return_on_focus_score(
        context=context,
        checkpoint=checkpoint,
        style_profile=style_profile,
        step_events=step_events,
    )
    goal_score = min(1.0, 0.55 + style_profile.trait_weights.pattern_hunting * 0.20)

    controller = AttentionController()
    attention = controller.decide(
        profile=style_profile,
        current_mode=current_mode,
        goal_score=goal_score,
        novelty_score=novelty_score,
        urgency_score=urgency_score,
        return_on_focus_score=return_on_focus_score,
        drift_score=drift_score,
        queued_interrupts=len(checkpoint.queued_interrupts) if checkpoint else 0,
        active_branch_count=1 + len(checkpoint.queued_branches) if checkpoint else 1,
        checkpoint_safe=checkpoint.safe_to_continue if checkpoint else True,
        steps_since_reanchor=steps_since_reanchor,
        novelty_budget_used=checkpoint.novelty_budget_used if checkpoint else 0,
        high_risk_pending=last_class in policy.approval_required_action_classes if last_class else False,
        kill_switch_active=kill_switch.active,
        primary_near_completion=context.state in {RuntimeState.reporting, RuntimeState.memory_commit},
        hyperfocus_steps_used=checkpoint.hyperfocus_steps_used if checkpoint else 0,
    )

    attention_evidence = {
        "attention_decision": attention.decision,
        "next_attention_mode": attention.next_mode.value,
        "goal_score": attention.goal_score,
        "novelty_score": attention.novelty_score,
        "urgency_score": attention.urgency_score,
        "return_on_focus_score": attention.return_on_focus_score,
        "drift_score": attention.drift_score,
        "steps": step_events,
        "retries": retry_events,
        "ledger_active_runs": ledger.active_runs,
        "style_profile_id": style_profile.profile_id,
    }

    if attention.decision == "reanchor_now":
        return EvaluatorReport(
            decision=EvaluatorDecision.reanchor,
            reason=attention.reason or "reanchor_required",
            evidence=attention_evidence,
            idempotency=idempotency,
            safe_to_continue=True,
        )

    if attention.decision == "switch_to_queued_interrupt":
        return EvaluatorReport(
            decision=EvaluatorDecision.switch_branch,
            reason=attention.reason or "switch_to_queued_interrupt",
            evidence=attention_evidence,
            idempotency=idempotency,
            safe_to_continue=True,
        )

    # 6. Default — observe with bounded style evidence.
    return EvaluatorReport(
        decision=EvaluatorDecision.continue_observe,
        reason="within_budget",
        evidence=attention_evidence,
        idempotency=idempotency,
        safe_to_continue=idempotency != Idempotency.non_idempotent,
    )
