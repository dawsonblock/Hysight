"""Metrics calculation for agent evaluation."""

from __future__ import annotations

from typing import Any, Dict, List

from hca.common.enums import ControlSignal, EventType, RuntimeState


def calculate_success_rate(runs: List[Dict[str, Any]]) -> float:
    if not runs:
        return 0.0
    completed = [
        run for run in runs if run.get("state") == RuntimeState.completed.value
    ]
    return len(completed) / len(runs)


def calculate_metacognitive_accuracy(events: List[Dict[str, Any]]) -> float:
    """Assess how often the meta-monitor correctly flagged issues."""
    assessments = [
        event
        for event in events
        if event.get("event_type") == EventType.meta_assessed.value
    ]
    if not assessments:
        return 1.0

    correct_detections = 0
    for assessment in assessments:
        payload = assessment.get("data", assessment.get("payload", {}))
        signal = payload.get("recommended_transition")
        has_anomalies = bool(
            payload.get("contradiction_flags")
            or payload.get("missing_information")
            or payload.get("self_limitations")
        )

        if has_anomalies and signal != ControlSignal.proceed.value:
            correct_detections += 1
        elif not has_anomalies and signal == ControlSignal.proceed.value:
            correct_detections += 1

    return correct_detections / len(assessments)


def calculate_tool_efficiency(receipts: List[Dict[str, Any]]) -> float:
    """Ratio of successful tool executions."""
    if not receipts:
        return 1.0
    successes = [
        receipt
        for receipt in receipts
        if receipt.get("status") == "success"
    ]
    return len(successes) / len(receipts)


def calculate_case_pass_rate(cases: List[Dict[str, Any]]) -> float:
    if not cases:
        return 0.0
    passed = [case for case in cases if case.get("passed")]
    return len(passed) / len(cases)


def calculate_completion_rate(cases: List[Dict[str, Any]]) -> float:
    if not cases:
        return 0.0
    completed = [
        case
        for case in cases
        if case.get("state") == RuntimeState.completed.value
    ]
    return len(completed) / len(cases)


def compute_metrics(result: dict) -> dict:
    """Compute metrics for a given run or harness result."""
    events = result.get("events", [])
    receipts = [
        event.get("data", event.get("payload"))
        for event in events
        if event.get("event_type") == EventType.execution_finished.value
    ]
    cases = result.get("cases", [])
    metrics: Dict[str, Any] = {
        "success_rate": (
            1.0
            if result.get("state") == RuntimeState.completed.value
            else 0.0
        ),
        "tool_efficiency": calculate_tool_efficiency(receipts),
        "metacognitive_accuracy": calculate_metacognitive_accuracy(events),
    }
    if cases:
        metrics["pass_rate"] = calculate_case_pass_rate(cases)
        metrics["case_count"] = len(cases)
        metrics["completion_rate"] = calculate_completion_rate(cases)
    explicit_metrics = result.get("metrics")
    if isinstance(explicit_metrics, dict):
        metrics.update(explicit_metrics)
    return metrics
