"""Action scoring logic."""

from typing import List, Tuple, Dict, Any

from hca.common.types import ActionCandidate


def score_actions(candidates: List[ActionCandidate]) -> List[Tuple[ActionCandidate, Dict[str, float]]]:
    """Return a list of (candidate, scores) sorted from highest to lowest overall score.

    The overall score is a weighted sum of the candidate's fields.  For the MVP,
    equal weights are used for expected progress, uncertainty reduction, reversibility, and policy alignment,
    minus weights for risk and cost.  Negative values reduce the total.
    """
    results: List[Tuple[ActionCandidate, Dict[str, float]]] = []
    for cand in candidates:
        scores = {
            "progress": cand.expected_progress,
            "uncertainty_reduction": cand.expected_uncertainty_reduction,
            "reversibility": cand.reversibility,
            "policy_alignment": cand.policy_alignment,
            "risk": -cand.risk,
            "cost": -cand.cost,
            "interruption": -cand.user_interruption_burden,
        }
        total = sum(scores.values())
        scores["total"] = total
        results.append((cand, scores))
    results.sort(key=lambda x: x[1]["total"], reverse=True)
    return results