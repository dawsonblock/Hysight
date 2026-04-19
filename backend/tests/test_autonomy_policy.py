"""Autonomy policy unit tests — structured decisions, not booleans."""

from hca.autonomy.policy import AutonomyBudget, AutonomyPolicy
from hca.common.enums import ActionClass, AutonomyMode


def _policy(**overrides) -> AutonomyPolicy:
    return AutonomyPolicy(**overrides)


def test_disabled_policy_rejects_trigger():
    policy = _policy(enabled=False)
    decision = policy.check_trigger("inbox")
    assert decision.allowed is False
    assert decision.reason == "autonomy_disabled"


def test_manual_mode_rejects_automatic_triggers():
    policy = _policy(mode=AutonomyMode.manual)
    decision = policy.check_trigger("schedule")
    assert decision.allowed is False
    assert decision.reason == "manual_mode_rejects_automatic_triggers"


def test_bounded_mode_accepts_inbox_trigger():
    policy = _policy(mode=AutonomyMode.bounded)
    decision = policy.check_trigger("inbox")
    assert decision.allowed is True


def test_budget_rejects_when_max_runs_exceeded():
    policy = _policy(budget=AutonomyBudget(max_runs_per_agent=1))
    decision = policy.check_budget(runs_launched=1, parallel_runs=0)
    assert decision.allowed is False
    assert decision.reason == "max_runs_per_agent_exceeded"


def test_budget_rejects_when_max_parallel_runs_exceeded():
    policy = _policy(budget=AutonomyBudget(max_parallel_runs=1))
    decision = policy.check_budget(runs_launched=0, parallel_runs=1)
    assert decision.allowed is False
    assert decision.reason == "max_parallel_runs_exceeded"


def test_budget_rejects_deadman_timeout():
    policy = _policy(budget=AutonomyBudget(deadman_timeout_seconds=5))
    decision = policy.check_budget(
        runs_launched=0,
        parallel_runs=0,
        run_duration_seconds=999.0,
    )
    assert decision.allowed is False
    assert decision.reason == "deadman_timeout_exceeded"


def test_action_binding_high_risk_requires_escalation():
    policy = _policy(
        approval_required_action_classes=[ActionClass.high.value]
    )
    decision = policy.check_action_binding(
        tool_name="write_file",
        action_class=ActionClass.high.value,
        requires_approval=False,
    )
    assert decision.allowed is False
    assert decision.reason == "action_class_requires_escalation"


def test_action_binding_low_risk_without_approval_is_allowed():
    policy = _policy(allowed_tool_names=["memory.retrieve"])
    decision = policy.check_action_binding(
        tool_name="memory.retrieve",
        action_class=ActionClass.low.value,
        requires_approval=False,
    )
    assert decision.allowed is True


def test_action_binding_tool_not_in_allowlist_rejected():
    policy = _policy(allowed_tool_names=["memory.retrieve"])
    decision = policy.check_action_binding(
        tool_name="shell.exec",
        action_class=ActionClass.low.value,
        requires_approval=False,
    )
    assert decision.allowed is False
    assert decision.reason == "tool_not_in_allowlist"


def test_action_binding_requires_approval_flag_blocks():
    policy = _policy(allowed_tool_names=[])
    decision = policy.check_action_binding(
        tool_name="memory.retrieve",
        action_class=ActionClass.low.value,
        requires_approval=True,
    )
    assert decision.allowed is False
    assert decision.reason == "action_requires_approval"


def test_check_resume_denies_when_auto_resume_disabled():
    policy = _policy(auto_resume_after_approval=False)
    decision = policy.check_resume(
        action_class=ActionClass.low.value, requires_approval=True
    )
    assert decision.allowed is False
    assert decision.reason == "auto_resume_disabled"


def test_check_resume_still_blocks_high_risk_class():
    policy = _policy(
        auto_resume_after_approval=True,
        approval_required_action_classes=[ActionClass.high.value],
    )
    decision = policy.check_resume(
        action_class=ActionClass.high.value, requires_approval=True
    )
    assert decision.allowed is False
    assert decision.reason == "action_class_requires_escalation"
