"""Proactivity harness for approval-gating proactive writes."""

from __future__ import annotations

from typing import Any, Dict, List

from hca.common.types import WorkspaceItem
from hca.evaluation.datasets import PROACTIVITY_CASES
from hca.meta.monitor import assess


def run() -> dict:
    cases: List[Dict[str, Any]] = []
    for case in PROACTIVITY_CASES:
        item = WorkspaceItem(
            source_module="evaluation",
            kind="action_suggestion",
            content={"action": case["action"], "args": case["args"]},
        )
        assessment = assess([item], proactive_intent_marker="proactive")
        cases.append(
            {
                "name": case["name"],
                "expected_signal": str(case["expected"].value),
                "signal": assessment.recommended_transition.value,
                "passed": (
                    assessment.recommended_transition == case["expected"]
                ),
            }
        )

    passed = len([case for case in cases if case["passed"]])
    return {
        "harness": "proactivity",
        "cases": cases,
        "metrics": {
            "guard_accuracy": passed / len(cases),
            "blocked_writes": len(
                [
                    case
                    for case in cases
                    if case["signal"] == "require_approval"
                ]
            ),
        },
    }
