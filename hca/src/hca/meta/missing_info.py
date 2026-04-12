"""Missing information detector for the workspace."""

from __future__ import annotations

from typing import List

from hca.common.types import MissingInfoResult, WorkspaceItem
from hca.executor.tool_registry import (
    ToolValidationError,
    get_tool,
    validate_tool_arguments,
)


def describe_missing_information(result: MissingInfoResult) -> str:
    if (
        result.missing_fields
        and not result.invalid_fields
        and not result.validation_errors
    ):
        fields = ", ".join(result.missing_fields)
        return (
            f"Action {result.action_kind} is missing required fields: "
            f"{fields}"
        )

    parts: List[str] = []
    if result.missing_fields:
        parts.append(
            f"missing required fields: {', '.join(result.missing_fields)}"
        )
    if result.invalid_fields:
        parts.append(f"invalid fields: {', '.join(result.invalid_fields)}")
    if result.validation_errors:
        parts.extend(result.validation_errors)

    if not parts:
        return f"Action {result.action_kind} is missing required information"
    return f"Action {result.action_kind} has invalid input: {'; '.join(parts)}"


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
        try:
            get_tool(action_kind)
        except KeyError:
            continue

        args = action.content.get("args", {})
        try:
            validate_tool_arguments(action_kind, args)
        except ToolValidationError as exc:
            missing.append(
                MissingInfoResult(
                    item_id=action.item_id,
                    action_kind=action_kind,
                    missing_fields=exc.missing_fields,
                    invalid_fields=exc.invalid_fields,
                    validation_errors=exc.validation_errors,
                )
            )
    return missing
