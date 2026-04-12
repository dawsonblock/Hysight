"""Bounded recurrence for the global workspace."""

from __future__ import annotations

from typing import Any, List, Optional

from hca.common.enums import EventType
from hca.common.types import RunContext, WorkspaceItem
from hca.storage.event_log import append_event
from hca.workspace.broadcast import broadcast
from hca.workspace.workspace import Workspace
from hca.workspace.ranking import score_item


def _coerce_workspace_items(values: List[Any]) -> List[WorkspaceItem]:
    items: List[WorkspaceItem] = []
    for value in values:
        if isinstance(value, WorkspaceItem):
            items.append(value)
        elif isinstance(value, dict):
            items.append(WorkspaceItem.model_validate(value))
    return items


def _winner(workspace: Workspace) -> Optional[WorkspaceItem]:
    actions = [
        item
        for item in workspace.items
        if item.kind == "action_suggestion"
    ]
    if not actions:
        return None
    return max(
        actions,
        key=lambda item: (item.confidence, item.score, item.item_id),
    )


def _apply_adjustments(
    workspace: Workspace,
    adjustments: List[dict[str, Any]],
) -> List[dict[str, Any]]:
    effects: List[dict[str, Any]] = []
    for adjustment in adjustments:
        delta = float(adjustment.get("delta", 0.0))
        target_item_id = adjustment.get("target_item_id")
        target_action = adjustment.get("target_action")
        for item in workspace.items:
            if item.kind != "action_suggestion":
                continue
            if target_item_id and item.item_id != target_item_id:
                continue
            if target_action and item.content.get("action") != target_action:
                continue
            before = item.confidence
            item.confidence = max(0.0, min(1.5, before + delta))
            item.score = score_item(item)
            effects.append(
                {
                    "item_id": item.item_id,
                    "delta": delta,
                    "reason": adjustment.get("reason"),
                    "before": before,
                    "after": item.confidence,
                }
            )
    return effects


def _summarize_revision_payloads(
    payloads: List[dict[str, Any]],
) -> List[dict[str, Any]]:
    summaries: List[dict[str, Any]] = []
    for payload in payloads:
        critique_items = payload.get("critique_items", [])
        summaries.append(
            {
                "source_module": payload.get("source_module"),
                "revised_proposal_count": len(
                    payload.get("revised_proposals", [])
                ),
                "confidence_adjustment_count": len(
                    payload.get("confidence_adjustments", [])
                ),
                "critique_items": critique_items,
            }
        )
    return summaries


def run_recurrence(
    workspace: Workspace,
    context: Optional[RunContext] = None,
    depth: int = 1,
    modules: Optional[List[Any]] = None,
) -> bool:
    """Perform a bounded recurrent update with deterministic revisions."""
    from hca.modules.critic import Critic
    from hca.modules.planner import Planner
    from hca.modules.tool_reasoner import ToolReasoner

    recurrence_modules = modules or [Planner(), Critic(), ToolReasoner()]
    changed = False
    for index in range(depth):
        prior_winner = _winner(workspace)
        revision_payloads = broadcast(workspace, recurrence_modules)
        new_candidates: List[WorkspaceItem] = []
        effects: List[dict[str, Any]] = []
        for payload in revision_payloads:
            revised_items = _coerce_workspace_items(
                payload.get("revised_proposals", [])
            )
            critique_items = _coerce_workspace_items(
                payload.get("critique_items", [])
            )
            for item in revised_items + critique_items:
                item.provenance.append(f"recurrence_depth_{index}")
            new_candidates.extend(revised_items + critique_items)
            effects.extend(
                _apply_adjustments(
                    workspace,
                    payload.get("confidence_adjustments", []),
                )
            )

        if new_candidates:
            workspace.admit(new_candidates)

        winner = _winner(workspace)
        if winner is not None:
            surviving_items: List[WorkspaceItem] = []
            evicted_ids: List[str] = []
            seen_winner = False
            for item in workspace.items:
                if item.kind == "action_suggestion":
                    if item.item_id == winner.item_id and not seen_winner:
                        surviving_items.append(item)
                        seen_winner = True
                    else:
                        evicted_ids.append(item.item_id)
                else:
                    surviving_items.append(item)
            workspace.items = surviving_items
            changed = changed or (
                prior_winner is not None
                and prior_winner.item_id != winner.item_id
            )
            if context and evicted_ids:
                append_event(
                    context,
                    EventType.workspace_evicted,
                    "recurrence",
                    {
                        "reason": "recurrence_winner",
                        "evicted_ids": evicted_ids,
                        "winner": winner.item_id,
                    },
                )

        if context:
            append_event(
                context,
                EventType.recurrent_pass_completed,
                "recurrence",
                {
                    "changed": changed,
                    "winner": winner.item_id if winner else None,
                    "effects": effects,
                    "revision_payloads": _summarize_revision_payloads(
                        revision_payloads
                    ),
                },
            )
    return changed
