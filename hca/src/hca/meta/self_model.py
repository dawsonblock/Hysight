"""Runtime self-model tracking agent limitations and capabilities."""

from __future__ import annotations

from typing import List

from hca.common.types import CapabilitySummary, WorkspaceItem
from hca.executor.tool_registry import list_tools


def supports_action(action_kind: str) -> bool:
    """Return True when the action is known to the runtime."""
    return action_kind in list_tools()


def capability_summary(
    items: List[WorkspaceItem] | None = None,
    failure_count: int = 0,
) -> CapabilitySummary:
    tools = list_tools()
    actions = [
        item for item in (items or []) if item.kind == "action_suggestion"
    ]
    unsupported = sorted(
        {
            action.content.get("action")
            for action in actions
            if isinstance(action.content.get("action"), str)
            and not supports_action(action.content.get("action"))
        }
    )
    return CapabilitySummary(
        available_tools=sorted(tools),
        approval_gated_tools=sorted(
            name for name, tool in tools.items() if tool.requires_approval
        ),
        unsupported_requested_actions=unsupported,
        failure_count=failure_count,
    )


def describe_capabilities() -> str:
    """Return a human-readable description of current capabilities."""
    summary = capability_summary()
    available = ", ".join(summary.available_tools)
    gated = ", ".join(summary.approval_gated_tools)
    return (
        f"Available tools: {available}. "
        f"Approval-gated tools: {gated or 'none'}."
    )


def check_self_limitations(
    items: List[WorkspaceItem],
    failure_count: int = 0,
) -> List[str]:
    """Identify whether the workspace exceeds current capabilities."""
    summary = capability_summary(items, failure_count=failure_count)
    limits = [
        f"Action '{action}' is beyond current capabilities."
        for action in summary.unsupported_requested_actions
    ]
    if not items:
        limits.append("No items in workspace to process.")
    return limits
