"""Autonomy policy and bounded budget model."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from hca.common.enums import ActionClass, AutonomyMode


class PolicyDecision(BaseModel):
    """Structured outcome returned by every ``AutonomyPolicy.check_*`` call."""

    allowed: bool
    reason: Optional[str] = None
    evidence: Dict[str, Any] = Field(default_factory=dict)


class AutonomyBudget(BaseModel):
    """Hard upper bounds an autonomy agent is allowed to consume."""

    max_steps_per_run: int = 50
    max_runs_per_agent: int = 25
    max_parallel_runs: int = 1
    max_retries_per_step: int = 2
    max_run_duration_seconds: int = 900
    deadman_timeout_seconds: int = 1800


class AutonomyPolicy(BaseModel):
    """Policy gating what a bounded autonomy agent may do.

    Structured decisions are returned from every ``check_*`` method, not plain
    booleans, so callers can emit precise rejection reasons into the event log.
    """

    mode: AutonomyMode = AutonomyMode.bounded
    enabled: bool = True
    budget: AutonomyBudget = Field(default_factory=AutonomyBudget)
    approval_required_action_classes: List[str] = Field(
        default_factory=lambda: [ActionClass.high.value]
    )
    allowed_tool_names: List[str] = Field(default_factory=list)
    allowed_network_domains: List[str] = Field(default_factory=list)
    allowed_workspace_roots: List[str] = Field(default_factory=list)
    allow_memory_writes: bool = True
    allow_external_writes: bool = False
    auto_resume_after_approval: bool = False

    def check_trigger(self, trigger_type: str) -> PolicyDecision:
        if not self.enabled:
            return PolicyDecision(
                allowed=False,
                reason="autonomy_disabled",
                evidence={"mode": self.mode.value},
            )
        if self.mode == AutonomyMode.manual:
            return PolicyDecision(
                allowed=False,
                reason="manual_mode_rejects_automatic_triggers",
                evidence={"mode": self.mode.value},
            )
        return PolicyDecision(
            allowed=True,
            evidence={
                "mode": self.mode.value,
                "trigger_type": trigger_type,
            },
        )

    def check_budget(
        self,
        *,
        runs_launched: int,
        parallel_runs: int,
        steps_in_current_run: int = 0,
        retries_for_current_step: int = 0,
        run_duration_seconds: float = 0.0,
    ) -> PolicyDecision:
        b = self.budget
        if runs_launched >= b.max_runs_per_agent:
            return PolicyDecision(
                allowed=False,
                reason="max_runs_per_agent_exceeded",
                evidence={
                    "runs_launched": runs_launched,
                    "max_runs_per_agent": b.max_runs_per_agent,
                },
            )
        if parallel_runs >= b.max_parallel_runs:
            return PolicyDecision(
                allowed=False,
                reason="max_parallel_runs_exceeded",
                evidence={
                    "parallel_runs": parallel_runs,
                    "max_parallel_runs": b.max_parallel_runs,
                },
            )
        if steps_in_current_run > b.max_steps_per_run:
            return PolicyDecision(
                allowed=False,
                reason="max_steps_per_run_exceeded",
                evidence={
                    "steps": steps_in_current_run,
                    "max_steps_per_run": b.max_steps_per_run,
                },
            )
        if retries_for_current_step > b.max_retries_per_step:
            return PolicyDecision(
                allowed=False,
                reason="max_retries_per_step_exceeded",
                evidence={
                    "retries": retries_for_current_step,
                    "max_retries_per_step": b.max_retries_per_step,
                },
            )
        if run_duration_seconds > b.deadman_timeout_seconds:
            return PolicyDecision(
                allowed=False,
                reason="deadman_timeout_exceeded",
                evidence={
                    "run_duration_seconds": run_duration_seconds,
                    "deadman_timeout_seconds": b.deadman_timeout_seconds,
                },
            )
        return PolicyDecision(
            allowed=True,
            evidence={
                "runs_launched": runs_launched,
                "parallel_runs": parallel_runs,
            },
        )

    def check_branching(
        self,
        *,
        requested_parallel_subgoals: int,
        style_parallel_limit: int,
        novelty_budget_remaining: int,
    ) -> PolicyDecision:
        hard_parallel_limit = min(
            max(1, requested_parallel_subgoals),
            max(1, self.budget.max_parallel_runs),
            max(1, style_parallel_limit),
        )
        if requested_parallel_subgoals > hard_parallel_limit:
            return PolicyDecision(
                allowed=False,
                reason="style_parallel_limit_exceeded",
                evidence={
                    "requested_parallel_subgoals": requested_parallel_subgoals,
                    "style_parallel_limit": style_parallel_limit,
                    "policy_parallel_limit": self.budget.max_parallel_runs,
                },
            )
        if novelty_budget_remaining < 0:
            return PolicyDecision(
                allowed=False,
                reason="novelty_budget_exhausted",
                evidence={"novelty_budget_remaining": novelty_budget_remaining},
            )
        return PolicyDecision(
            allowed=True,
            evidence={
                "requested_parallel_subgoals": requested_parallel_subgoals,
                "style_parallel_limit": style_parallel_limit,
                "novelty_budget_remaining": novelty_budget_remaining,
            },
        )

    def check_action_binding(
        self,
        *,
        tool_name: Optional[str],
        action_class: Optional[str],
        requires_approval: bool,
    ) -> PolicyDecision:
        if tool_name is not None and self.allowed_tool_names:
            if tool_name not in self.allowed_tool_names:
                return PolicyDecision(
                    allowed=False,
                    reason="tool_not_in_allowlist",
                    evidence={
                        "tool_name": tool_name,
                        "allowed_tool_names": list(self.allowed_tool_names),
                    },
                )
        if action_class is not None and (
            action_class in self.approval_required_action_classes
        ):
            return PolicyDecision(
                allowed=False,
                reason="action_class_requires_escalation",
                evidence={"action_class": action_class},
            )
        if requires_approval:
            return PolicyDecision(
                allowed=False,
                reason="action_requires_approval",
                evidence={"tool_name": tool_name},
            )
        return PolicyDecision(
            allowed=True,
            evidence={
                "tool_name": tool_name,
                "action_class": action_class,
            },
        )

    def check_resume(
        self,
        *,
        action_class: Optional[str],
        requires_approval: bool,
    ) -> PolicyDecision:
        if not self.auto_resume_after_approval:
            return PolicyDecision(
                allowed=False,
                reason="auto_resume_disabled",
                evidence={"mode": self.mode.value},
            )
        if action_class is not None and (
            action_class in self.approval_required_action_classes
        ):
            return PolicyDecision(
                allowed=False,
                reason="action_class_requires_escalation",
                evidence={"action_class": action_class},
            )
        return PolicyDecision(
            allowed=True,
            evidence={"requires_approval": requires_approval},
        )
