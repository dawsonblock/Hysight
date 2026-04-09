"""Metacognition evaluation harness."""

from __future__ import annotations

from typing import Any, Dict, List

from hca.common.enums import MemoryType
from hca.common.types import MemoryRecord, RetrievalItem, WorkspaceItem
from hca.evaluation.datasets import METACOGNITION_CASES
from hca.meta.monitor import assess


def evaluate_metacognition(run_id: str) -> dict:
    """Evaluate the metacognitive performance of a specific run."""
    return {"run_id": run_id, "evaluated": True}


def _build_items(scenario: str) -> List[WorkspaceItem]:
    if scenario == "clean":
        return [
            WorkspaceItem(
                source_module="test",
                kind="action_suggestion",
                content={"action": "echo", "args": {"text": "hello"}},
            ),
            WorkspaceItem(
                source_module="test",
                kind="perceived_intent",
                content={"goal": "hello"},
            )
        ]
    if scenario == "contradiction":
        record = MemoryRecord(
            run_id="eval",
            memory_type=MemoryType.episodic,
            subject="status",
            content="old",
            contradiction_status=True,
        )
        return [
            WorkspaceItem(
                source_module="test",
                kind="memory_retrieval",
                content=[
                    RetrievalItem(
                        record=record,
                        confidence=1.0,
                        contradiction=True,
                        staleness=0.1,
                        memory_type=MemoryType.episodic,
                    )
                ],
            )
        ]
    if scenario == "missing_info":
        return [
            WorkspaceItem(
                source_module="test",
                kind="action_suggestion",
                content={"action": "store_note", "args": {}},
            )
        ]
    if scenario == "unsupported":
        return [
            WorkspaceItem(
                source_module="test",
                kind="action_suggestion",
                content={"action": "calculate", "args": {"x": 1}},
            )
        ]
    return []


def run_metacognition_harness() -> Dict[str, Any]:
    """Test the meta-monitor's ability to detect workspace anomalies."""
    results = []
    for case in METACOGNITION_CASES:
        assessment = assess(_build_items(case["scenario"]))
        passed = assessment.recommended_transition == case["expected"]
        results.append(
            {
                "case": case["name"],
                "passed": passed,
                "expected_signal": str(case["expected"].value),
                "signal": assessment.recommended_transition.value,
                "reason_code": assessment.reason_code,
                "explanation": assessment.explanation,
            }
        )

    passed_count = len([result for result in results if result["passed"]])
    return {
        "harness": "metacognition",
        "cases": results,
        "metrics": {
            "accuracy": passed_count / len(METACOGNITION_CASES),
            "case_count": len(METACOGNITION_CASES),
        },
    }


def run() -> dict:
    """Entry point for CLI."""
    return run_metacognition_harness()
