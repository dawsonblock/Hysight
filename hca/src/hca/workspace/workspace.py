"""Global Workspace for the hybrid cognitive agent."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from hca.workspace.ranking import score_item
from hca.common.types import WorkspaceItem
from hca.common.time import utc_now


class Workspace:
    """A small, capacity-limited workspace for active items."""

    def __init__(self, capacity: int = 7) -> None:
        self.capacity = capacity
        self.items: List[WorkspaceItem] = []

    def _conflict_penalty(self, item: WorkspaceItem) -> float:
        penalty = 0.0
        if item.conflict_refs:
            penalty += 0.15 * len(item.conflict_refs)
        if item.kind == "action_suggestion":
            item_action = item.content.get("action")
            item_args = item.content.get("args", {})
            for existing in self.items:
                if existing.kind != "action_suggestion":
                    continue
                existing_action = existing.content.get("action")
                existing_args = existing.content.get("args", {})
                if (
                    item_action != existing_action
                    or item_args != existing_args
                ):
                    penalty += 0.15
                    break
        return penalty

    def _effective_score(self, item: WorkspaceItem) -> float:
        return score_item(item) - self._conflict_penalty(item)

    def admit(
        self, candidates: List[WorkspaceItem]
    ) -> Tuple[List[WorkspaceItem], List[WorkspaceItem], List[WorkspaceItem]]:
        """Attempt to admit candidate items into the workspace.
        Returns a tuple of (accepted, rejected, evicted).
        """
        accepted: List[WorkspaceItem] = []
        rejected: List[WorkspaceItem] = []
        evicted: List[WorkspaceItem] = []

        scored = [
            (item, self._effective_score(item), self._conflict_penalty(item))
            for item in candidates
        ]
        scored.sort(
            key=lambda entry: (
                entry[1],
                entry[0].confidence,
                entry[0].item_id,
            ),
            reverse=True,
        )

        for item, score, penalty in scored:
            item.score = score
            if score < 0.0:
                item.admission_reason = "rejected_below_floor"
                rejected.append(item)
                continue
            if len(self.items) < self.capacity:
                item.admitted_at = item.admitted_at or utc_now()
                item.admission_reason = "accepted_capacity_available"
                self.items.append(item)
                accepted.append(item)
            else:
                current_with_scores = [
                    (existing, self._effective_score(existing))
                    for existing in self.items
                ]
                worst_item, worst_score = min(
                    current_with_scores,
                    key=lambda entry: (entry[1], entry[0].item_id),
                )

                if score > worst_score:
                    self.items.remove(worst_item)
                    worst_item.admission_reason = "evicted_lower_score"
                    evicted.append(worst_item)
                    item.admitted_at = item.admitted_at or utc_now()
                    item.admission_reason = "accepted_replaced_lower_score"
                    self.items.append(item)
                    accepted.append(item)
                else:
                    item.admission_reason = (
                        "rejected_conflict_penalty"
                        if penalty > 0.0
                        else "rejected_below_floor"
                    )
                    rejected.append(item)

        return accepted, rejected, evicted

    def broadcast(self) -> List[WorkspaceItem]:
        """Return current items for broadcasting to modules."""
        return list(self.items)

    def summary(self) -> Dict[str, Any]:
        """Summarize the current workspace state."""
        counts: Dict[str, int] = {}
        for item in self.items:
            counts[item.kind] = counts.get(item.kind, 0) + 1

        return counts
