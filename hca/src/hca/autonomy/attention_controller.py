"""Bounded attention control for operator-style autonomy behavior."""

from __future__ import annotations

from typing import Any, Dict

from pydantic import BaseModel, Field

from hca.autonomy.style_profile import AttentionMode, OperatorStyleProfile


class AttentionDecision(BaseModel):
    decision: str
    next_mode: AttentionMode
    goal_score: float = Field(default=0.0, ge=0.0, le=1.0)
    novelty_score: float = Field(default=0.0, ge=0.0, le=1.0)
    urgency_score: float = Field(default=0.0, ge=0.0, le=1.0)
    return_on_focus_score: float = Field(default=0.0, ge=0.0, le=1.0)
    drift_score: float = Field(default=0.0, ge=0.0, le=1.0)
    checkpoint_required: bool = False
    reason: str = ""
    evidence: Dict[str, Any] = Field(default_factory=dict)


class AttentionController:
    """Small bounded prioritization layer around the existing supervisor.

    The controller never launches work on its own. It only recommends whether
    the existing supervisor should stay on the current thread, queue a new
    interrupt, re-anchor, or allow a bounded side branch.
    """

    def decide(
        self,
        *,
        profile: OperatorStyleProfile,
        current_mode: AttentionMode,
        goal_score: float,
        novelty_score: float,
        urgency_score: float,
        return_on_focus_score: float,
        drift_score: float,
        queued_interrupts: int,
        active_branch_count: int,
        checkpoint_safe: bool,
        steps_since_reanchor: int,
        novelty_budget_used: int,
        high_risk_pending: bool,
        kill_switch_active: bool,
        primary_near_completion: bool,
        hyperfocus_steps_used: int,
    ) -> AttentionDecision:
        traits = profile.trait_weights
        weighted_goal = min(1.0, goal_score + traits.pattern_hunting * 0.10)
        weighted_novelty = min(
            1.0,
            novelty_score
            + traits.novelty_seeking * 0.20
            + traits.non_linear_planning * 0.05,
        )
        weighted_urgency = min(1.0, urgency_score + traits.interrupt_sensitivity * 0.15)
        weighted_return = min(1.0, return_on_focus_score + traits.hyperfocus_bursting * 0.10)
        weighted_drift = min(
            1.0,
            drift_score
            + traits.time_blindness_risk * 0.10
            + (0.1 if queued_interrupts else 0.0),
        )
        novelty_budget_remaining = max(
            0, profile.novelty_exploration_budget - novelty_budget_used
        )

        evidence = {
            "max_parallel_subgoals": profile.max_parallel_subgoals,
            "novelty_budget_remaining": novelty_budget_remaining,
            "queued_interrupts": queued_interrupts,
            "active_branch_count": active_branch_count,
            "current_mode": current_mode.value,
        }

        if kill_switch_active or high_risk_pending:
            return AttentionDecision(
                decision="stay_on_primary",
                next_mode=AttentionMode.stable,
                goal_score=weighted_goal,
                novelty_score=weighted_novelty,
                urgency_score=weighted_urgency,
                return_on_focus_score=weighted_return,
                drift_score=weighted_drift,
                checkpoint_required=False,
                reason="kill_switch_or_high_risk_pending",
                evidence=evidence,
            )

        if steps_since_reanchor >= profile.reanchor_interval_steps or weighted_drift >= 0.72:
            return AttentionDecision(
                decision="reanchor_now",
                next_mode=AttentionMode.reanchor,
                goal_score=weighted_goal,
                novelty_score=weighted_novelty,
                urgency_score=weighted_urgency,
                return_on_focus_score=weighted_return,
                drift_score=weighted_drift,
                checkpoint_required=True,
                reason="reanchor_interval_or_drift_threshold",
                evidence=evidence,
            )

        if current_mode == AttentionMode.hyperfocus:
            if hyperfocus_steps_used >= profile.hyperfocus_max_steps:
                return AttentionDecision(
                    decision="exit_hyperfocus",
                    next_mode=AttentionMode.reanchor,
                    goal_score=weighted_goal,
                    novelty_score=weighted_novelty,
                    urgency_score=weighted_urgency,
                    return_on_focus_score=weighted_return,
                    drift_score=weighted_drift,
                    checkpoint_required=True,
                    reason="hyperfocus_step_budget_exceeded",
                    evidence=evidence,
                )
            if weighted_novelty < 0.55 or weighted_goal >= weighted_novelty + 0.20:
                return AttentionDecision(
                    decision="reject_branch",
                    next_mode=AttentionMode.hyperfocus,
                    goal_score=weighted_goal,
                    novelty_score=weighted_novelty,
                    urgency_score=weighted_urgency,
                    return_on_focus_score=weighted_return,
                    drift_score=weighted_drift,
                    checkpoint_required=False,
                    reason="hyperfocus_suppresses_low_value_novelty",
                    evidence=evidence,
                )

        if active_branch_count >= profile.max_parallel_subgoals:
            return AttentionDecision(
                decision="reject_branch",
                next_mode=current_mode,
                goal_score=weighted_goal,
                novelty_score=weighted_novelty,
                urgency_score=weighted_urgency,
                return_on_focus_score=weighted_return,
                drift_score=weighted_drift,
                checkpoint_required=False,
                reason="max_parallel_subgoals_reached",
                evidence=evidence,
            )

        if novelty_budget_remaining <= 0 and weighted_novelty >= weighted_goal:
            return AttentionDecision(
                decision="reject_branch",
                next_mode=current_mode,
                goal_score=weighted_goal,
                novelty_score=weighted_novelty,
                urgency_score=weighted_urgency,
                return_on_focus_score=weighted_return,
                drift_score=weighted_drift,
                checkpoint_required=False,
                reason="novelty_budget_exhausted",
                evidence=evidence,
            )

        if queued_interrupts > 0 and weighted_urgency >= 0.85:
            if checkpoint_safe and not primary_near_completion:
                return AttentionDecision(
                    decision="switch_to_queued_interrupt",
                    next_mode=AttentionMode.exploratory,
                    goal_score=weighted_goal,
                    novelty_score=weighted_novelty,
                    urgency_score=weighted_urgency,
                    return_on_focus_score=weighted_return,
                    drift_score=weighted_drift,
                    checkpoint_required=profile.forced_checkpoint_before_switch,
                    reason="urgent_interrupt_with_safe_checkpoint",
                    evidence=evidence,
                )
            return AttentionDecision(
                decision="queue_interrupt",
                next_mode=current_mode,
                goal_score=weighted_goal,
                novelty_score=weighted_novelty,
                urgency_score=weighted_urgency,
                return_on_focus_score=weighted_return,
                drift_score=weighted_drift,
                checkpoint_required=profile.forced_checkpoint_before_switch,
                reason="urgent_interrupt_but_primary_should_finish_first",
                evidence=evidence,
            )

        if (
            current_mode != AttentionMode.hyperfocus
            and weighted_return >= 0.82
            and weighted_goal >= 0.70
        ):
            return AttentionDecision(
                decision="enter_hyperfocus",
                next_mode=AttentionMode.hyperfocus,
                goal_score=weighted_goal,
                novelty_score=weighted_novelty,
                urgency_score=weighted_urgency,
                return_on_focus_score=weighted_return,
                drift_score=weighted_drift,
                checkpoint_required=False,
                reason="strong_return_on_focus_signal",
                evidence=evidence,
            )

        if weighted_novelty >= 0.70 and novelty_budget_remaining > 0:
            return AttentionDecision(
                decision="allow_branch",
                next_mode=AttentionMode.exploratory,
                goal_score=weighted_goal,
                novelty_score=weighted_novelty,
                urgency_score=weighted_urgency,
                return_on_focus_score=weighted_return,
                drift_score=weighted_drift,
                checkpoint_required=profile.forced_checkpoint_before_switch,
                reason="bounded_novelty_branch_allowed",
                evidence=evidence,
            )

        return AttentionDecision(
            decision="stay_on_primary",
            next_mode=AttentionMode.stable if weighted_goal >= weighted_novelty else current_mode,
            goal_score=weighted_goal,
            novelty_score=weighted_novelty,
            urgency_score=weighted_urgency,
            return_on_focus_score=weighted_return,
            drift_score=weighted_drift,
            checkpoint_required=False,
            reason="primary_goal_still_best",
            evidence=evidence,
        )
