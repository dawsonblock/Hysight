"""Conflict detector for identifying overlaps in the workspace."""

from __future__ import annotations

from typing import List

from hca.common.types import ConflictRecord, WorkspaceItem


def detect_conflicts(items: List[WorkspaceItem]) -> List[ConflictRecord]:
    """Return structured conflicts between workspace items."""
    conflicts: List[ConflictRecord] = []
    actions = [item for item in items if item.kind == "action_suggestion"]
    for index, item in enumerate(actions):
        for other in actions[index + 1:]:
            item_action = item.content.get("action")
            other_action = other.content.get("action")
            if item_action != other_action:
                conflicts.append(
                    ConflictRecord(
                        item_ids=[item.item_id, other.item_id],
                        reason_code="different_action_kind",
                        details={
                            "actions": [item_action, other_action],
                        },
                    )
                )
                continue

            item_args = item.content.get("args", {})
            other_args = other.content.get("args", {})
            if item_args != other_args:
                conflicts.append(
                    ConflictRecord(
                        item_ids=[item.item_id, other.item_id],
                        reason_code="different_action_args",
                        details={
                            "action": item_action,
                            "args": [item_args, other_args],
                        },
                    )
                )

    contradiction_items = [
        item.item_id for item in items if item.contradiction_status
    ]
    if contradiction_items:
        conflicts.append(
            ConflictRecord(
                item_ids=contradiction_items,
                reason_code="memory_contradiction",
            )
        )
    return conflicts
