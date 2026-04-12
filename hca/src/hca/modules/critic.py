"""Critic module.

LLM-powered evaluation of proposed plans using Claude Sonnet 4.5.

The Critic operates in two phases:
  1. ``propose(run_id)``  — stores run_id for later; returns an empty proposal.
  2. ``on_broadcast(items)`` — called after all modules have proposed; uses the
     stored run_id to load the goal and evaluates the plan via LLM.

Falls back to rule-based checks when the LLM call fails.
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
from typing import Any, Dict, List, Optional, Union

from hca.common.types import (
    ConflictRecord,
    MissingInfoResult,
    ModuleProposal,
    WorkspaceItem,
)
from hca.meta.conflict_detector import detect_conflicts
from hca.meta.missing_info import (
    describe_missing_information,
    detect_missing_information,
)
from hca.storage import load_run

# Thread-local storage so concurrent requests each carry their own run_id.
_tl = threading.local()

# LLM critique.

_CRITIC_SYSTEM = """
You are the Critic module of a Hybrid Cognitive Agent (HCA).
Your role is to evaluate the proposed plan produced by the Planner module.

Given the agent's GOAL and the PROPOSED ACTION, assess:
1. Alignment   — does the action directly serve the goal? (0.0–1.0)
2. Feasibility — is the action executable with available tools? (0.0–1.0)
3. Safety      — are there risks, side-effects, or misuse potential? (0.0–1.0)

Then decide:
    "approve"  — the plan looks good; confidence_delta in [0.0, +0.05]
    "revise"   — the plan needs adjustment; confidence_delta in [-0.15, 0.0]
    "reject"   — the plan is unsafe or badly misaligned;
                             confidence_delta in [-0.3, -0.15]

Respond ONLY with valid JSON — no markdown fences, no extra text:
{
    "verdict": "approve|revise|reject",
    "alignment": 0.0,
    "feasibility": 0.0,
    "safety": 0.0,
    "issues": [],
    "confidence_delta": 0.0,
    "rationale": "one sentence"
}
"""


async def _llm_evaluate(
    goal: str,
    action: str,
    rationale: str,
) -> Dict[str, Any]:
    """Call Claude Sonnet 4.5 to evaluate the proposed action."""
    from emergentintegrations.llm.chat import (  # type: ignore
        LlmChat,
        UserMessage,
    )

    api_key = os.environ.get("EMERGENT_LLM_KEY", "")
    session_id = f"critic-{id(_tl)}"
    chat = (
        LlmChat(
            api_key=api_key,
            session_id=session_id,
            system_message=_CRITIC_SYSTEM,
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")
    )

    prompt = (
        f"GOAL: {goal}\n\n"
        f"PROPOSED ACTION: {action}\n\n"
        f"PLANNER RATIONALE: {rationale}"
    )
    response = await chat.send_message(UserMessage(text=prompt))

    # Parse JSON from LLM response (strip any accidental markdown fences).
    raw = response.strip().strip("```json").strip("```").strip()
    return json.loads(raw)


def _format_conflict_issue(conflict: ConflictRecord) -> str:
    """Render a stable, human-readable issue from a structured conflict."""
    details = conflict.details or {}

    if conflict.reason_code == "different_action_kind":
        actions = [
            str(action) for action in details.get("actions", []) if action
        ]
        if actions:
            return f"Conflicting actions proposed: {' vs '.join(actions)}"
        return "Conflicting actions proposed"

    if conflict.reason_code == "different_action_args":
        action = details.get("action")
        if action:
            return f"Action {action} has conflicting arguments"
        return "Action has conflicting arguments"

    if conflict.reason_code == "memory_contradiction":
        return "Workspace contains contradiction-linked items"

    item_ids = ", ".join(conflict.item_ids)
    reason = conflict.reason_code.replace("_", " ")
    if item_ids:
        return f"{reason} (items: {item_ids})"
    return reason


def _format_missing_info_issue(result: MissingInfoResult) -> str:
    """Render a stable, human-readable issue from a structured gap."""
    return describe_missing_information(result)


def _rule_based_critique(
    items: List[WorkspaceItem],
) -> Dict[str, Any]:
    """Fast rule-based fallback that never fails."""
    conflicts = detect_conflicts(items)
    missing = detect_missing_information(items)

    issues = [
        *(_format_conflict_issue(conflict) for conflict in conflicts),
        *(_format_missing_info_issue(result) for result in missing),
    ]
    delta = -0.05 * len(conflicts) - 0.02 * len(missing)
    verdict = "revise" if issues else "approve"

    return {
        "verdict": verdict,
        "alignment": 0.7,
        "feasibility": 0.8,
        "safety": 0.9,
        "issues": issues,
        "confidence_delta": max(delta, -0.3),
        "rationale": (
            f"Rule-based: {len(conflicts)} conflict(s), "
            f"{len(missing)} gap(s)."
        ),
        "llm_powered": False,
        "fallback_reason": "rule_based_only",
    }


# Critic class.


class Critic:
    name = "critic"

    def propose(
        self, input_data: Union[str, List[WorkspaceItem]]
    ) -> ModuleProposal:
        """Store the run_id for use in on_broadcast."""
        if isinstance(input_data, str):
            _tl.run_id = input_data  # thread-local, safe for concurrent runs
        return ModuleProposal(
            source_module=self.name,
            candidate_items=[],
            rationale="Critic defers evaluation to on_broadcast phase.",
            confidence=1.0,
        )

    def on_broadcast(
        self, items: List[WorkspaceItem]
    ) -> Dict[str, Any]:
        """Evaluate workspace items after all modules have proposed."""
        run_id: Optional[str] = getattr(_tl, "run_id", None)

        # Get goal from the stored run.
        goal = ""
        if run_id:
            run = load_run(run_id)
            goal = run.goal if run else ""

        # Extract the plan from workspace items.
        plan_item = next(
            (
                i for i in items
                if i.kind in ("task_plan", "action_suggestion")
            ),
            None,
        )
        action = ""
        rationale = ""
        if plan_item:
            action = plan_item.content.get("action", str(plan_item.content))
            rationale = plan_item.content.get("rationale", "")

        # LLM critique with rule-based fallback.
        critique: Dict[str, Any] = {}
        fallback_reason: Optional[str] = None
        if goal and action:
            try:
                critique = asyncio.run(_llm_evaluate(goal, action, rationale))
                critique.setdefault("llm_powered", True)
            except Exception as exc:
                import logging
                logging.getLogger(__name__).warning(
                    "LLM critic failed, falling back to rule-based: %s", exc
                )
                fallback_reason = f"llm_error:{exc.__class__.__name__}"

        if not critique:
            critique = _rule_based_critique(items)
        if fallback_reason is not None:
            critique["fallback_reason"] = fallback_reason
        critique.setdefault("fallback_reason", None)

        # Build confidence adjustments for workspace items.
        delta = float(critique.get("confidence_delta", 0.0))
        adjustments = []
        for item in items:
            if item.kind in ("task_plan", "action_suggestion"):
                adjustments.append(
                    {
                        "item_id": item.item_id,
                        "new_confidence": max(
                            0.0,
                            min(1.0, item.confidence + delta),
                        ),
                        "reason": critique.get("rationale", ""),
                    }
                )

        # Emit a critic item so the trace UI shows the verdict.
        critique_workspace_item = WorkspaceItem(
            source_module=self.name,
            kind="critic_verdict",
            content={
                "verdict": critique.get("verdict", "approve"),
                "alignment": critique.get("alignment", 1.0),
                "feasibility": critique.get("feasibility", 1.0),
                "safety": critique.get("safety", 1.0),
                "issues": critique.get("issues", []),
                "confidence_delta": delta,
                "rationale": critique.get("rationale", ""),
                "llm_powered": bool(critique.get("llm_powered", False)),
                "fallback_reason": critique.get("fallback_reason"),
            },
            salience=0.6,
            confidence=1.0,
        )

        return {
            "revised_proposals": [],
            "confidence_adjustments": adjustments,
            "critique_items": [
                critique_workspace_item.model_dump(mode="json")
            ],
        }
