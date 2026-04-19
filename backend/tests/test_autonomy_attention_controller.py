"""Attention controller tests for the bounded operator-style cognition layer."""

from hca.autonomy.attention_controller import AttentionController
from hca.autonomy.style_profile import AttentionMode, get_style_profile


def test_urgent_interrupt_switches_only_when_checkpoint_is_safe():
    controller = AttentionController()
    profile = get_style_profile("dawson_like_operator")

    queued = controller.decide(
        profile=profile,
        current_mode=AttentionMode.stable,
        goal_score=0.7,
        novelty_score=0.3,
        urgency_score=0.95,
        return_on_focus_score=0.4,
        drift_score=0.2,
        queued_interrupts=1,
        active_branch_count=1,
        checkpoint_safe=False,
        steps_since_reanchor=1,
        novelty_budget_used=0,
        high_risk_pending=False,
        kill_switch_active=False,
        primary_near_completion=False,
        hyperfocus_steps_used=0,
    )
    assert queued.decision == "queue_interrupt"

    switched = controller.decide(
        profile=profile,
        current_mode=AttentionMode.stable,
        goal_score=0.7,
        novelty_score=0.3,
        urgency_score=0.95,
        return_on_focus_score=0.4,
        drift_score=0.2,
        queued_interrupts=1,
        active_branch_count=1,
        checkpoint_safe=True,
        steps_since_reanchor=1,
        novelty_budget_used=0,
        high_risk_pending=False,
        kill_switch_active=False,
        primary_near_completion=False,
        hyperfocus_steps_used=0,
    )
    assert switched.decision == "switch_to_queued_interrupt"


def test_hyperfocus_suppresses_low_value_branch_creation():
    controller = AttentionController()
    profile = get_style_profile("dawson_like_operator")

    decision = controller.decide(
        profile=profile,
        current_mode=AttentionMode.hyperfocus,
        goal_score=0.92,
        novelty_score=0.25,
        urgency_score=0.2,
        return_on_focus_score=0.85,
        drift_score=0.1,
        queued_interrupts=0,
        active_branch_count=1,
        checkpoint_safe=True,
        steps_since_reanchor=1,
        novelty_budget_used=0,
        high_risk_pending=False,
        kill_switch_active=False,
        primary_near_completion=False,
        hyperfocus_steps_used=1,
    )
    assert decision.decision == "reject_branch"


def test_max_branch_count_is_enforced():
    controller = AttentionController()
    profile = get_style_profile("dawson_like_operator")

    decision = controller.decide(
        profile=profile,
        current_mode=AttentionMode.exploratory,
        goal_score=0.55,
        novelty_score=0.9,
        urgency_score=0.5,
        return_on_focus_score=0.4,
        drift_score=0.15,
        queued_interrupts=0,
        active_branch_count=profile.max_parallel_subgoals,
        checkpoint_safe=True,
        steps_since_reanchor=1,
        novelty_budget_used=0,
        high_risk_pending=False,
        kill_switch_active=False,
        primary_near_completion=False,
        hyperfocus_steps_used=0,
    )
    assert decision.decision == "reject_branch"


def test_forced_reanchor_happens_on_interval():
    controller = AttentionController()
    profile = get_style_profile("conservative_operator")

    decision = controller.decide(
        profile=profile,
        current_mode=AttentionMode.stable,
        goal_score=0.8,
        novelty_score=0.2,
        urgency_score=0.2,
        return_on_focus_score=0.7,
        drift_score=0.25,
        queued_interrupts=0,
        active_branch_count=1,
        checkpoint_safe=True,
        steps_since_reanchor=profile.reanchor_interval_steps,
        novelty_budget_used=0,
        high_risk_pending=False,
        kill_switch_active=False,
        primary_near_completion=False,
        hyperfocus_steps_used=0,
    )
    assert decision.decision == "reanchor_now"


def test_novelty_budget_exhaustion_blocks_new_branches():
    controller = AttentionController()
    profile = get_style_profile("dawson_like_operator")

    decision = controller.decide(
        profile=profile,
        current_mode=AttentionMode.exploratory,
        goal_score=0.5,
        novelty_score=0.95,
        urgency_score=0.4,
        return_on_focus_score=0.3,
        drift_score=0.2,
        queued_interrupts=0,
        active_branch_count=1,
        checkpoint_safe=True,
        steps_since_reanchor=1,
        novelty_budget_used=profile.novelty_exploration_budget,
        high_risk_pending=False,
        kill_switch_active=False,
        primary_near_completion=False,
        hyperfocus_steps_used=0,
    )
    assert decision.decision == "reject_branch"
