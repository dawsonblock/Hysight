"""Action scoring logic."""

from typing import Dict, List, Tuple

from hca.common.types import ActionCandidate


def score_actions(
    candidates: List[ActionCandidate],
) -> List[Tuple[ActionCandidate, Dict[str, float]]]:
    """Return scored candidates sorted from highest to lowest total."""

    results: List[Tuple[ActionCandidate, Dict[str, float]]] = []
    for cand in candidates:
        feasibility = max(
            0.0,
            1.0
            - (
                (cand.risk * 0.5)
                + (cand.cost * 0.3)
                + (cand.user_interruption_burden * 0.2)
            ),
        )
        scores = {
            "progress": cand.expected_progress,
            "uncertainty_reduction": cand.expected_uncertainty_reduction,
            "reversibility": cand.reversibility,
            "policy_alignment": cand.policy_alignment,
            "feasibility": feasibility,
            "risk": -cand.risk,
            "cost": -cand.cost,
            "interruption": -cand.user_interruption_burden,
        }
        total = sum(scores.values())
        scores["total"] = total
        results.append((cand, scores))
    results.sort(key=lambda x: x[1]["total"], reverse=True)
    return results
