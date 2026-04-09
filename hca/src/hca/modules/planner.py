"""Simple planner module for proposing strategies."""

from __future__ import annotations

from typing import List, Union
from hca.common.types import ModuleProposal, WorkspaceItem


class Planner:
    name = "planner"

    def update(self, items: List[WorkspaceItem]) -> None:
        """Update internal state based on workspace content."""
        pass

    def on_broadcast(self, items: List[WorkspaceItem]):
        perceived_intent = None
        current_strategy = None
        critiques: List[str] = []
        for item in items:
            if item.kind == "perceived_intent":
                perceived_intent = item.content.get("intent")
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
        self, input_data: Union[str, List[WorkspaceItem]]
    ) -> ModuleProposal:
        """Build a small plan from actual intent or broadcast items."""

        current_items = input_data if isinstance(input_data, list) else []

        perceived_intent = None
        for item in current_items:
            if item.kind == "perceived_intent":
                perceived_intent = item.content.get("intent")
                break

        strategy = "single_action_dispatch"
        if perceived_intent == "store":
            strategy = "memory_persistence_strategy"
        elif perceived_intent == "retrieve":
            strategy = "information_retrieval_strategy"

        item = WorkspaceItem(
            source_module=self.name,
            kind="task_plan",
            content={
                "strategy": strategy,
                "perceived_intent": perceived_intent,
            },
            salience=0.6,
            confidence=1.0,
        )

        return ModuleProposal(
            source_module=self.name,
            candidate_items=[item],
            rationale=f"Plan to dispatch action with strategy: {strategy}.",
            confidence=1.0,
        )
