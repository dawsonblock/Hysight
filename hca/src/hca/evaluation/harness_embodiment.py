"""Embodiment harness for file-producing actions."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from hca.api.runtime_actions import auto_grant_pending_approval
from hca.evaluation.datasets import EMBODIMENT_CASES
from hca.runtime.replay import reconstruct_state
from hca.runtime.runtime import Runtime
from hca.storage import iter_artifacts


def _execute_goal(goal: str) -> Dict[str, Any]:
    runtime = Runtime()
    run_id = runtime.run(goal)
    run_id = auto_grant_pending_approval(
        run_id,
        actor="evaluation",
        token_prefix="eval",
    )

    replay = reconstruct_state(run_id)
    artifacts = list(iter_artifacts(run_id))
    paths = [
        str(artifact.get("path"))
        for artifact in artifacts
        if artifact.get("path")
    ]
    return {
        "run_id": run_id,
        "state": replay.get("state"),
        "selected_action": replay.get("selected_action_kind"),
        "artifacts": paths,
        "files_exist": all(Path(path).exists() for path in paths),
    }


def run() -> dict:
    cases: List[Dict[str, Any]] = []
    for case in EMBODIMENT_CASES:
        observed = _execute_goal(str(case["goal"]))
        cases.append(
            {
                **case,
                **observed,
                "passed": (
                    observed["selected_action"] == case["expected_action"]
                    and bool(observed["artifacts"])
                    and observed["files_exist"]
                ),
            }
        )

    passed = len([case for case in cases if case["passed"]])
    return {
        "harness": "embodiment",
        "cases": cases,
        "metrics": {
            "artifact_success_rate": passed / len(cases),
            "artifact_count": sum(len(case["artifacts"]) for case in cases),
        },
    }
