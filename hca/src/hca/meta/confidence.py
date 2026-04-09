"""Confidence estimation stub."""

from typing import List

from hca.common.types import WorkspaceItem


def estimate_overall_confidence(items: List[WorkspaceItem]) -> float:
    if not items:
        return 1.0
    # simple average of confidence
    return sum(item.confidence for item in items) / len(items)