"""Action and workflow scoring logic."""

from typing import Dict, List, Tuple

from hca.common.types import ActionCandidate, WorkflowPlan
from hca.executor.tool_registry import get_tool


def score_actions(
    candidates: List[ActionCandidate],
) -> List[Tuple[ActionCandidate, Dict[str, float]]]:
    """Return scored candidates sorted from highest to lowest total."""

    results: List[Tuple[ActionCandidate, Dict[str, float]]] = []
    for cand in candidates:
        feasibility = max(
            0.0,
            1.0
            - (
                (cand.risk * 0.5)
                + (cand.cost * 0.3)
                + (cand.user_interruption_burden * 0.2)
            ),
        )
        scores = {
            "progress": cand.expected_progress,
            "uncertainty_reduction": cand.expected_uncertainty_reduction,
            "reversibility": cand.reversibility,
            "policy_alignment": cand.policy_alignment,
            "feasibility": feasibility,
            "risk": -cand.risk,
            "cost": -cand.cost,
            "interruption": -cand.user_interruption_burden,
        }
        total = sum(scores.values())
        scores["total"] = total
        results.append((cand, scores))
    results.sort(key=lambda x: x[1]["total"], reverse=True)
    return results


def _workflow_step_policy(
    tool_name: str,
    arguments_template: Dict[str, float],
) -> Dict[str, float]:
    tool = get_tool(tool_name)
    requires_approval = float(tool.requires_approval)
    risk = tool.risk
    cost = tool.cost
    interruption = tool.user_interruption_burden
    if (
        tool_name in {"patch_text_file", "replace_in_file"}
        and not arguments_template.get("apply", False)
    ):
        requires_approval = 0.0
        risk = min(risk, 0.08)
        cost = min(cost, 0.08)
        interruption = 0.0
    return {
        "requires_approval": requires_approval,
        "risk": risk,
        "cost": cost,
        "interruption": interruption,
    }


def score_workflow_plans(
    plans: List[WorkflowPlan],
) -> List[Tuple[WorkflowPlan, Dict[str, float]]]:
    """Return workflow plans scored by bounded completion quality."""

    results: List[Tuple[WorkflowPlan, Dict[str, float]]] = []
    evidence_tools = {
        "summarize_search_results",
        "investigate_workspace_issue",
        "create_diff_report",
        "create_run_report",
    }
    verification_tools = {"run_command", "run_tests_subset"}

    for plan in plans:
        step_policies = [
            _workflow_step_policy(step.tool_name, step.arguments_template)
            for step in plan.steps
        ]
        max_steps = max(plan.max_steps, 1)
        plan_length = len(plan.steps)
        approval_steps = sum(
            1.0 for policy in step_policies if policy["requires_approval"]
        )
        total_risk = sum(policy["risk"] for policy in step_policies)
        total_cost = sum(policy["cost"] for policy in step_policies)
        total_interruption = sum(
            policy["interruption"] for policy in step_policies
        )
        evidence_count = sum(
            1.0 for step in plan.steps if step.tool_name in evidence_tools
        )
        has_verification = any(
            step.tool_name in verification_tools for step in plan.steps
        )
        has_final_report = any(
            step.tool_name == "create_run_report" for step in plan.steps
        )

        feasibility = 1.0 if plan_length <= max_steps else max(
            0.0, 1.0 - ((plan_length - max_steps) * 0.2)
        )
        evidence_score = min(
            1.0,
            (evidence_count * 0.35) + (0.3 if has_final_report else 0.0),
        )
        risk_score = max(0.0, 1.0 - min(1.0, total_risk))
        policy_cost = max(
            0.0,
            1.0 - min(1.0, (approval_steps * 0.18) + total_interruption),
        )
        completion_likelihood = max(
            0.0,
            1.0
            - min(1.0, ((plan_length / max_steps) * 0.55) + total_cost),
        )
        verification_bonus = 0.2 if has_verification else 0.0

        scores = {
            "feasibility": feasibility,
            "evidence": evidence_score,
            "risk_score": risk_score,
            "policy_cost": policy_cost,
            "completion_likelihood": completion_likelihood,
            "verification_bonus": verification_bonus,
            "confidence": plan.confidence,
            "total": 0.0,
        }
        scores["total"] = (
            (feasibility * 1.2)
            + evidence_score
            + risk_score
            + policy_cost
            + completion_likelihood
            + verification_bonus
            + (plan.confidence * 0.5)
        )
        results.append((plan, scores))

    results.sort(key=lambda item: item[1]["total"], reverse=True)
    return results
