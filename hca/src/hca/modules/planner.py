"""Planner module — LLM-powered strategic planning via Claude Sonnet 4.5.

Falls back to rule-based planning if the LLM call fails.
"""
from __future__ import annotations

import asyncio
import json
import os
import uuid
from time import perf_counter
from typing import Any, List, Union

from hca.common.types import ModuleProposal, WorkspaceItem, WorkflowPlan
from hca.executor.tool_registry import tool_prompt_catalog
from hca.modules.workflow_chains import (
    build_workflow_plan,
    resolve_step_arguments,
)
from hca.modules.workspace_intents import infer_workspace_action_from_text
from hca.storage import load_run


def _system_prompt() -> str:
    return (
        "You are the Planner module of a Hybrid Cognitive Agent (HCA). "
        "Given a user goal and any relevant memory context, produce a "
        "structured execution plan.\n\n"
        "Available strategies:\n"
        "  single_action_dispatch         — one-shot action\n"
        "  bounded_workflow_chain         — bounded multi-step chain\n"
        "  memory_persistence_strategy    — store information to memory\n"
        "  information_retrieval_strategy — retrieve information "
        "from memory\n"
        "  artifact_authoring_strategy    — write content to a "
        "bounded artifact path\n"
        "  workspace_inspection_strategy  — inspect repository "
        "files or directories\n"
        "  workspace_mutation_strategy    — patch one bounded text file\n"
        "  investigation_strategy         — gather evidence and emit "
        "a structured report\n"
        "  contract_drift_strategy        — contrast target-local and "
        "broader contract evidence before reporting\n"
        "  mutation_verification_strategy — inspect, patch, verify, "
        "and report within a bounded chain\n"
        "  run_reporting_strategy         — summarize the current run\n\n"
        f"Available actions:\n{tool_prompt_catalog()}\n\n"
        "Respond ONLY with valid JSON — no markdown fences, no extra keys:\n"
        "{\n"
        '    "strategy": "<strategy>",\n'
        '    "action": "<action or null>",\n'
        '    "action_args": {"<key>": "<value>"},\n'
        '    "workflow_class": "<workflow_class or null>",\n'
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
    workflow_plan = build_workflow_plan(goal)
    if workflow_plan is not None:
        return {
            "strategy": workflow_plan.strategy,
            "workflow_plan": workflow_plan,
            "action": workflow_plan.steps[0].tool_name,
            "action_args": resolve_step_arguments(
                workflow_plan,
                workflow_plan.steps[0],
                step_history=[],
            ),
            "confidence": max(0.7, workflow_plan.confidence),
            "rationale": workflow_plan.rationale,
        }

    workspace_action, workspace_args = infer_workspace_action_from_text(goal)

    def _strategy_for_action(action: str) -> str:
        if action in {"patch_text_file", "replace_in_file"}:
            return "workspace_mutation_strategy"
        if action == "create_run_report":
            return "run_reporting_strategy"
        if action == "investigate_workspace_issue":
            return "investigation_strategy"
        return "workspace_inspection_strategy"

    if perceived_intent == "store":
        return {
            "strategy": "memory_persistence_strategy",
            "action": "store_note",
            "action_args": {"note": goal},
            "confidence": 0.6,
            "rationale": "Rule-based: goal contains store/remember intent.",
        }
    if perceived_intent == "retrieve":
        if workspace_action is not None:
            return {
                "strategy": _strategy_for_action(workspace_action),
                "action": workspace_action,
                "action_args": workspace_args,
                "confidence": 0.6,
                "rationale": (
                    "Rule-based: retrieval goal maps to a bounded "
                    "workspace action."
                ),
            }
        return {
            "strategy": "information_retrieval_strategy",
            "action": "echo",
            "action_args": {"text": f"Searching memory for: {goal}"},
            "confidence": 0.6,
            "rationale": "Rule-based: goal contains retrieval intent.",
        }
    if workspace_action is not None:
        return {
            "strategy": _strategy_for_action(workspace_action),
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
        memory_hits: List[dict[str, Any]] = []
        memory_retrieval_latency_ms: float | None = None
        memory_retrieval_status = "not_attempted"
        memory_retrieval_error: str | None = None
        if goal:
            try:
                from memory_service.singleton import (  # type: ignore
                    get_controller,
                )
                from memory_service import RetrievalQuery  # type: ignore

                retrieval_started_at = perf_counter()
                hits = get_controller().retrieve(
                    RetrievalQuery(query_text=goal, top_k=3, run_id=run_id)
                )
                memory_retrieval_latency_ms = round(
                    (perf_counter() - retrieval_started_at) * 1000.0,
                    3,
                )
                memory_retrieval_status = "retrieved"
                memory_hits = [
                    {
                        "text": hit.text,
                        "score": round(hit.score, 3),
                        "memory_type": hit.memory_type,
                        "stored_at": (
                            hit.stored_at.isoformat()
                            if hit.stored_at is not None
                            else None
                        ),
                    }
                    for hit in hits
                ]
                if hits:
                    memory_context = "\n".join(
                        f"- [{h.memory_type}] {h.text} (score={h.score:.2f})"
                        for h in hits
                    )
            except Exception as exc:
                memory_retrieval_status = "failed"
                memory_retrieval_error = exc.__class__.__name__

        plan: dict[str, Any] | None
        workflow_plan = build_workflow_plan(goal) if goal else None
        planning_mode = "rule_based_only"
        fallback_reason: str | None = None
        if workflow_plan is not None:
            plan = {
                "strategy": workflow_plan.strategy,
                "workflow_plan": workflow_plan,
                "action": workflow_plan.steps[0].tool_name,
                "action_args": resolve_step_arguments(
                    workflow_plan,
                    workflow_plan.steps[0],
                    step_history=[],
                ),
                "confidence": max(0.72, workflow_plan.confidence),
                "rationale": workflow_plan.rationale,
            }
            plan_from_llm = False
            planning_mode = "workflow_chain"
        else:
            # LLM planning
            plan = None
            plan_from_llm = False
            llm_error: str | None = None
            if goal:
                try:
                    plan = asyncio.run(_llm_plan(goal, memory_context))
                    plan_from_llm = True
                    planning_mode = "llm"
                except Exception as exc:
                    llm_error = exc.__class__.__name__

            if plan is None:
                plan = _rule_based_plan(perceived_intent, goal)
                planning_mode = "rule_based_fallback"
                if llm_error is not None:
                    fallback_reason = f"llm_error:{llm_error}"
                elif goal:
                    fallback_reason = "rule_based_only"
                else:
                    fallback_reason = "missing_goal"

        assert plan is not None

        workflow_plan_payload = plan.get("workflow_plan")
        workflow_class = None
        workflow_id = None
        if isinstance(workflow_plan_payload, WorkflowPlan):
            workflow_class = workflow_plan_payload.workflow_class.value
            workflow_id = workflow_plan_payload.workflow_id

        action_args = plan.get("action_args", {})
        if not isinstance(action_args, dict):
            action_args = {}

        strategy = str(plan.get("strategy", "single_action_dispatch"))
        action = plan.get("action")
        if not isinstance(action, str) or not action:
            action = "echo"
        confidence_value = plan.get("confidence", 0.8)
        if isinstance(confidence_value, (int, float)):
            confidence = float(confidence_value)
        else:
            confidence = 0.8
        rationale = str(plan.get("rationale", "LLM-generated plan."))

        plan_item = WorkspaceItem(
            source_module=self.name,
            kind="task_plan",
            content={
                "strategy": strategy,
                "action": action,
                "action_args": action_args,
                "workflow_class": workflow_class,
                "workflow_id": workflow_id,
                "rationale": rationale,
                "llm_planned": plan_from_llm,
                "memory_context_used": bool(memory_hits),
                "planning_mode": planning_mode,
                "fallback_reason": fallback_reason,
                "memory_hits": memory_hits,
                "memory_retrieval_latency_ms": memory_retrieval_latency_ms,
                "memory_retrieval_status": memory_retrieval_status,
                "memory_retrieval_error": memory_retrieval_error,
            },
            salience=0.7,
            confidence=confidence,
        )

        candidate_items = [plan_item]

        if isinstance(workflow_plan_payload, WorkflowPlan):
            candidate_items.append(
                WorkspaceItem(
                    source_module=self.name,
                    kind="workflow_plan",
                    content=workflow_plan_payload.model_dump(mode="json"),
                    salience=0.9,
                    confidence=confidence,
                )
            )

        action_item = WorkspaceItem(
            source_module=self.name,
            kind="action_suggestion",
            content={
                "action": action,
                "args": action_args,
            },
            salience=0.85,
            confidence=confidence,
        )
        candidate_items.append(action_item)

        return ModuleProposal(
            source_module=self.name,
            candidate_items=candidate_items,
            rationale=rationale,
            confidence=confidence,
        )
