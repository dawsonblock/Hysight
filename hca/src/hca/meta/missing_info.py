"""Missing information detector for the workspace."""

from __future__ import annotations

from typing import Dict, List

from hca.common.types import MissingInfoResult, WorkspaceItem


_REQUIRED_ARGS: Dict[str, List[str]] = {
    "echo": ["text"],
    "store_note": ["note"],
    "write_artifact": ["content"],
}


def detect_missing_information(
    items: List[WorkspaceItem],
) -> List[MissingInfoResult]:
    """Identify action suggestions that are missing required arguments."""
    missing: List[MissingInfoResult] = []
    actions = [item for item in items if item.kind == "action_suggestion"]
    for action in actions:
        action_kind = action.content.get("action")
        if not isinstance(action_kind, str):
            continue
        args = action.content.get("args", {})
        missing_fields = [
            field
            for field in _REQUIRED_ARGS.get(action_kind, [])
            if not args.get(field)
        ]
        if missing_fields:
            missing.append(
                MissingInfoResult(
                    item_id=action.item_id,
                    action_kind=action_kind,
                    missing_fields=missing_fields,
                )
            )
    return missing
