"""Planner module — LLM-powered strategic planning via Claude Sonnet 4.5.

Falls back to rule-based planning if the LLM call fails.
"""
from __future__ import annotations

import asyncio
import json
import os
import uuid
from typing import List, Union

from hca.common.types import ModuleProposal, WorkspaceItem
from hca.executor.tool_registry import tool_prompt_catalog
from hca.modules.workspace_intents import infer_workspace_action_from_text
from hca.storage import load_run


def _system_prompt() -> str:
    return (
        "You are the Planner module of a Hybrid Cognitive Agent (HCA). "
        "Given a user goal and any relevant memory context, produce a "
        "structured execution plan.\n\n"
        "Available strategies:\n"
        "  single_action_dispatch         — one-shot action\n"
        "  memory_persistence_strategy    — store information to memory\n"
        "  information_retrieval_strategy — retrieve information "
        "from memory\n"
        "  artifact_authoring_strategy    — write content to a "
        "bounded artifact path\n"
        "  workspace_inspection_strategy  — inspect repository "
        "files or directories\n\n"
        f"Available actions:\n{tool_prompt_catalog()}\n\n"
        "Respond ONLY with valid JSON — no markdown fences, no extra keys:\n"
        "{\n"
        '    "strategy": "<strategy>",\n'
        '    "action": "<action>",\n'
        '    "action_args": {"<key>": "<value>"},\n'
        '    "confidence": 0.85,\n'
        '    "rationale": "<one concise sentence>"\n'
        "}"
    )


async def _llm_plan(goal: str, memory_context: str) -> dict:
    from emergentintegrations.llm.chat import (  # type: ignore
        LlmChat,
        UserMessage,
    )

    api_key = os.environ.get("EMERGENT_LLM_KEY", "")
    chat = LlmChat(
        api_key=api_key,
        session_id=f"planner-{uuid.uuid4().hex[:8]}",
        system_message=_system_prompt(),
    ).with_model("anthropic", "claude-sonnet-4-5-20250929")

    prompt = f"Goal: {goal}"
    if memory_context:
        prompt += f"\n\nRelevant memory context:\n{memory_context}"

    response = await chat.send_message(UserMessage(text=prompt))
    text = response.strip()
    # Strip markdown code fences if model adds them
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1] if len(parts) > 1 else text
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


def _rule_based_plan(perceived_intent: str | None, goal: str) -> dict:
    """Deterministic fallback when LLM is unavailable."""
    workspace_action, workspace_args = infer_workspace_action_from_text(goal)

    if perceived_intent == "store":
        return {
            "strategy": "memory_persistence_strategy",
            "action": "store_note",
            "action_args": {"note": goal},
            "confidence": 0.6,
            "rationale": "Rule-based: goal contains store/remember intent.",
        }
    if perceived_intent == "retrieve":
        return {
            "strategy": "information_retrieval_strategy",
            "action": "echo",
            "action_args": {"text": f"Searching memory for: {goal}"},
            "confidence": 0.6,
            "rationale": "Rule-based: goal contains retrieval intent.",
        }
    if workspace_action is not None:
        return {
            "strategy": "workspace_inspection_strategy",
            "action": workspace_action,
            "action_args": workspace_args,
            "confidence": 0.65,
            "rationale": (
                "Rule-based: goal requests bounded workspace inspection."
            ),
        }
    return {
        "strategy": "single_action_dispatch",
        "action": "echo",
        "action_args": {"text": goal or "Hello from HCA."},
        "confidence": 0.55,
        "rationale": "Rule-based fallback: general intent.",
    }


class Planner:
    name = "planner"

    def update(self, items: List[WorkspaceItem]) -> None:
        pass

    def on_broadcast(self, items: List[WorkspaceItem]):
        perceived_intent = None
        raw_goal = ""
        current_strategy = None
        critiques: List[str] = []
        for item in items:
            if item.kind == "perceived_intent":
                perceived_intent = item.content.get("intent")
                raw_goal = item.content.get("raw_goal", "")
            elif item.kind == "task_plan":
                current_strategy = item.content.get("strategy")
            elif item.kind == "action_critique":
                critiques.extend(item.content.get("critiques", []))

        target_strategy = current_strategy or "single_action_dispatch"
        target_action = None
        if perceived_intent == "store":
            target_strategy = "memory_persistence_strategy"
            target_action = "store_note"
        elif perceived_intent == "retrieve":
            target_strategy = "information_retrieval_strategy"
            target_action = "echo"
        elif perceived_intent == "write":
            target_strategy = "artifact_authoring_strategy"
            target_action = "write_artifact"
        else:
            inferred_action, _ = infer_workspace_action_from_text(raw_goal)
            if inferred_action is not None:
                target_strategy = "workspace_inspection_strategy"
                target_action = inferred_action

        revised_proposals = []
        if target_strategy != current_strategy:
            revised_proposals.append(
                WorkspaceItem(
                    source_module=self.name,
                    kind="task_plan",
                    content={
                        "strategy": target_strategy,
                        "perceived_intent": perceived_intent,
                        "revised": True,
                    },
                    salience=0.65,
                    confidence=1.0,
                )
            )

        adjustments = []
        for item in items:
            if item.kind != "action_suggestion":
                continue
            action = item.content.get("action")
            if target_action and action == target_action:
                adjustments.append(
                    {
                        "target_item_id": item.item_id,
                        "delta": 0.12,
                        "reason": "plan_alignment",
                    }
                )
            elif target_action and action != target_action:
                adjustments.append(
                    {
                        "target_item_id": item.item_id,
                        "delta": -0.05,
                        "reason": "plan_misalignment",
                    }
                )
            if critiques:
                adjustments.append(
                    {
                        "target_item_id": item.item_id,
                        "delta": -0.04,
                        "reason": "critic_feedback",
                    }
                )

        return {
            "revised_proposals": revised_proposals,
            "confidence_adjustments": adjustments,
            "critique_items": [],
        }

    def propose(
        self,
        input_data: Union[str, List[WorkspaceItem]],
    ) -> ModuleProposal:
        """Build a plan using Claude Sonnet 4.5 with rule-based fallback."""
        current_items = input_data if isinstance(input_data, list) else []

        # Extract existing intent from workspace (if re-planning)
        perceived_intent = None
        for item in current_items:
            if item.kind == "perceived_intent":
                perceived_intent = item.content.get("intent")
                break

        goal = ""
        run_id = None
        if isinstance(input_data, str):
            run_id = input_data
            run = load_run(input_data)
            goal = run.goal if run else ""

        # Pull relevant memory context for grounding
        memory_context = ""
        if goal:
            try:
                from memory_service.singleton import (  # type: ignore
                    get_controller,
                )
                from memory_service import RetrievalQuery  # type: ignore

                hits = get_controller().retrieve(
                    RetrievalQuery(query_text=goal, top_k=3, run_id=run_id)
                )
                if hits:
                    memory_context = "\n".join(
                        f"- [{h.memory_type}] {h.text} (score={h.score:.2f})"
                        for h in hits
                    )
            except Exception:
                pass

        # LLM planning
        plan = None
        if goal:
            try:
                plan = asyncio.run(_llm_plan(goal, memory_context))
            except Exception:
                pass

        if not plan:
            plan = _rule_based_plan(perceived_intent, goal)

        plan_item = WorkspaceItem(
            source_module=self.name,
            kind="task_plan",
            content={
                "strategy": plan.get("strategy", "single_action_dispatch"),
                "action": plan.get("action"),
                "action_args": plan.get("action_args", {}),
                "rationale": plan.get("rationale", ""),
                "llm_planned": True,
                "memory_context_used": bool(memory_context),
            },
            salience=0.7,
            confidence=plan.get("confidence", 0.8),
        )

        action_item = WorkspaceItem(
            source_module=self.name,
            kind="action_suggestion",
            content={
                "action": plan.get("action", "echo"),
                "args": plan.get("action_args", {}),
            },
            salience=0.85,
            confidence=plan.get("confidence", 0.8),
        )

        return ModuleProposal(
            source_module=self.name,
            candidate_items=[plan_item, action_item],
            rationale=plan.get("rationale", "LLM-generated plan."),
            confidence=plan.get("confidence", 0.8),
        )
