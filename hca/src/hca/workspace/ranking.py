"""Ranking logic for workspace admission."""

from hca.common.types import WorkspaceItem


def score_item(item: WorkspaceItem) -> float:
    """Compute a score for a workspace item.

    This MVP uses a simple sum of salience, utility and confidence, minus uncertainty.
    """
    return item.salience + item.utility_estimate + item.confidence - item.uncertainty