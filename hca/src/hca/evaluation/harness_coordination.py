"""Coordination harness for testing module-to-action alignment."""

from __future__ import annotations

from typing import Any, Dict, List

from hca.api.runtime_actions import auto_grant_pending_approval
from hca.common.enums import EventType, RuntimeState
from hca.evaluation.datasets import COORDINATION_CASES
from hca.runtime.replay import reconstruct_state
from hca.runtime.runtime import Runtime
from hca.storage import iter_events, load_run


def _execute_goal(goal: str) -> Dict[str, Any]:
    runtime = Runtime()
    run_id = runtime.run(goal)
    approval_used = False
    context = load_run(run_id)
    if context and context.pending_approval_id:
        run_id = auto_grant_pending_approval(
            run_id,
            actor="evaluation",
            token_prefix="eval",
        )
        approval_used = True

    replay = reconstruct_state(run_id)
    events = list(iter_events(run_id))
    return {
        "run_id": run_id,
        "state": replay.get("state"),
        "selected_action": replay.get("selected_action_kind"),
        "approval_used": approval_used,
        "module_proposals": len(
            [
                event
                for event in events
                if event["event_type"] == EventType.module_proposed.value
            ]
        ),
        "recurrent_passes": len(
            [
                event
                for event in events
                if event["event_type"]
                == EventType.recurrent_pass_completed.value
            ]
        ),
    }


def run() -> dict:
    cases: List[Dict[str, Any]] = []
    for case in COORDINATION_CASES:
        observed = _execute_goal(str(case["goal"]))
        passed = (
            observed["selected_action"] == case["expected_action"]
            and observed["state"] == RuntimeState.completed.value
        )
        cases.append({**case, **observed, "passed": passed})

    completed = len(
        [
            case
            for case in cases
            if case["state"] == RuntimeState.completed.value
        ]
    )
    correct = len([case for case in cases if case["passed"]])
    approval_cases = [case for case in cases if case["requires_approval"]]
    approval_success = len(
        [
            case
            for case in approval_cases
            if case["approval_used"] and case["passed"]
        ]
    )
    return {
        "harness": "coordination",
        "cases": cases,
        "metrics": {
            "completion_rate": completed / len(cases),
            "selection_accuracy": correct / len(cases),
            "approval_resume_rate": (
                approval_success / len(approval_cases)
                if approval_cases
                else 1.0
            ),
        },
    }
