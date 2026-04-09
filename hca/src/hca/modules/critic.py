"""Critic module for validating proposals."""

from __future__ import annotations

from typing import List, Union
from hca.common.types import ModuleProposal, WorkspaceItem
from hca.executor.tool_registry import get_tool
from hca.meta.conflict_detector import detect_conflicts
from hca.meta.missing_info import detect_missing_information


class Critic:
    name = "critic"

    def update(self, items: List[WorkspaceItem]) -> None:
        """Update internal state based on workspace content."""
        pass

    def on_broadcast(self, items: List[WorkspaceItem]):
        conflicts = detect_conflicts(items)
        missing = detect_missing_information(items)
        critiques: List[str] = []
        adjustments = []
        for conflict in conflicts:
            critiques.append(f"Conflict detected: {conflict.reason_code}")
            for item_id in conflict.item_ids:
                adjustments.append(
                    {
                        "target_item_id": item_id,
                        "delta": -0.15,
                        "reason": conflict.reason_code,
                    }
                )

        for missing_result in missing:
            critiques.append(
                f"Missing {', '.join(missing_result.missing_fields)} for "
                f"{missing_result.action_kind}"
            )
            adjustments.append(
                {
                    "target_item_id": missing_result.item_id,
                    "delta": -0.2,
                    "reason": "missing_required_input",
                }
            )

        critique_items = []
        if critiques:
            critique_items.append(
                WorkspaceItem(
                    source_module=self.name,
                    kind="action_critique",
                    content={"critiques": critiques},
                    salience=0.75,
                    confidence=1.0,
                )
            )

        return {
            "revised_proposals": [],
            "confidence_adjustments": adjustments,
            "critique_items": critique_items,
        }

    def propose(
        self, input_data: Union[str, List[WorkspaceItem]]
    ) -> ModuleProposal:
        """Validate action candidates in workspace."""

        current_items = input_data if isinstance(input_data, list) else []
        critiques = []

        for item in current_items:
            if item.kind == "action_suggestion":
                action = item.content.get("action")
                args = item.content.get("args", {})

                try:
                    get_tool(action)
                except (ValueError, KeyError):
                    critiques.append(f"Unknown tool: {action}")
                    continue

                if action == "store_note" and "note" not in args:
                    critiques.append(
                        "Missing required argument 'note' for store_note"
                    )
                elif action == "write_artifact" and (
                    "content" not in args or "path" not in args
                ):
                    critiques.append(
                        "Missing 'content' or 'path' for write_artifact"
                    )
                elif action == "echo" and "text" not in args:
                    critiques.append("Missing 'text' for echo")

        if not critiques and current_items:
            critiques = ["No obvious issues detected in proposed actions."]

        if not current_items:
            return ModuleProposal(
                source_module=self.name,
                candidate_items=[],
                rationale="No items to critique.",
            )

        item = WorkspaceItem(
            source_module=self.name,
            kind="action_critique",
            content={"critiques": critiques},
            salience=0.7,
            confidence=1.0,
        )

        return ModuleProposal(
            source_module=self.name,
            candidate_items=[item],
            rationale="Validated action candidates against tool registry.",
            confidence=1.0,
        )
