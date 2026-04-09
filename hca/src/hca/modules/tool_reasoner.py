"""Tool reasoning module for proposing action candidates."""

from __future__ import annotations

from typing import List, Union
from hca.common.types import ModuleProposal, WorkspaceItem
from hca.storage import load_run


class ToolReasoner:
    name = "tool_reasoner"

    def update(self, items: List[WorkspaceItem]) -> None:
        """Update internal state based on workspace content."""
        pass

    def on_broadcast(self, items: List[WorkspaceItem]):
        intent_class = None
        perceived_arguments = {}
        strategy = None
        critiques: List[str] = []
        for item in items:
            if item.kind == "perceived_intent":
                intent_class = item.content.get("intent_class")
                perceived_arguments = item.content.get("arguments", {})
            elif item.kind == "task_plan":
                strategy = item.content.get("strategy")
            elif item.kind == "action_critique":
                critiques.extend(item.content.get("critiques", []))

        revised_proposals = []
        desired_action = None
        desired_args = {}
        if intent_class == "store_note":
            desired_action = "store_note"
            desired_args = {
                "note": perceived_arguments.get(
                    "note", perceived_arguments.get("text", "")
                )
            }
        elif intent_class == "retrieve_memory":
            desired_action = "echo"
            desired_args = {
                "text": (
                    f"Searching for: {perceived_arguments.get('query')}"
                )
            }
        elif intent_class == "write_artifact":
            desired_action = "write_artifact"
            desired_args = dict(perceived_arguments)

        if desired_action and not any(
            item.kind == "action_suggestion"
            and item.content.get("action") == desired_action
            for item in items
        ):
            revised_proposals.append(
                WorkspaceItem(
                    source_module=self.name,
                    kind="action_suggestion",
                    content={"action": desired_action, "args": desired_args},
                    salience=0.9,
                    confidence=0.95,
                )
            )

        adjustments = []
        for item in items:
            if item.kind != "action_suggestion":
                continue
            action = item.content.get("action")
            delta = 0.0
            reasons: List[str] = []
            if intent_class == "store_note" and action == "store_note":
                delta += 0.12
                reasons.append("perception_alignment")
            elif (
                intent_class == "write_artifact"
                and action == "write_artifact"
            ):
                delta += 0.12
                reasons.append("perception_alignment")
            elif intent_class == "retrieve_memory" and action == "echo":
                delta += 0.05
                reasons.append("perception_alignment")

            if (
                strategy == "memory_persistence_strategy"
                and action == "store_note"
            ):
                delta += 0.08
                reasons.append("plan_alignment")
            elif (
                strategy == "artifact_authoring_strategy"
                and action == "write_artifact"
            ):
                delta += 0.08
                reasons.append("plan_alignment")

            if critiques:
                delta -= 0.08
                reasons.append("critique")

            if action == "write_artifact" and intent_class != "write_artifact":
                delta -= 0.2
                reasons.append("proactive_risk")

            if delta != 0.0:
                adjustments.append(
                    {
                        "target_item_id": item.item_id,
                        "delta": delta,
                        "reason": "+".join(reasons),
                    }
                )

        return {
            "revised_proposals": revised_proposals,
            "confidence_adjustments": adjustments,
            "critique_items": [],
        }

    def propose(
        self, input_data: Union[str, List[WorkspaceItem]]
    ) -> ModuleProposal:
        """Select tools based on intent and plan strategy."""

        current_items = input_data if isinstance(input_data, list) else []

        strategy = None
        intent_class = None
        args = {}
        for item in current_items:
            if item.kind == "task_plan":
                strategy = item.content.get("strategy")
            elif item.kind == "perceived_intent":
                intent_class = item.content.get("intent_class")
                args = item.content.get("arguments", {})

        if not intent_class and isinstance(input_data, str):
            run = load_run(input_data)
            goal = run.goal if run else ""
            goal_lower = goal.lower()
            if "note" in goal_lower or "remember" in goal_lower:
                intent_class = "store_note"
                args = {"note": goal}
            else:
                intent_class = "general"
                args = {"text": goal}

        action = "echo"
        final_args = {}

        if intent_class == "store_note":
            action = "store_note"
            final_args = {"note": args.get("text", args.get("note", ""))}
        elif intent_class == "retrieve_memory":
            action = "echo"
            final_args = {"text": f"Searching for: {args.get('query')}"}
        elif intent_class == "write_artifact":
            action = "write_artifact"
            final_args = args
        else:
            action = "echo"
            final_args = {"text": args.get("text", "hello")}

        confidence = 1.0
        if strategy == "single_action_dispatch":
            confidence = 1.0
        elif strategy is None:
            confidence = 0.8

        item = WorkspaceItem(
            source_module=self.name,
            kind="action_suggestion",
            content={"action": action, "args": final_args},
            salience=0.9,
            confidence=confidence,
        )

        return ModuleProposal(
            source_module=self.name,
            candidate_items=[item],
            rationale=(
                f"Selected {action} with confidence {confidence} "
                f"based on strategy {strategy}."
            ),
            confidence=confidence,
        )
