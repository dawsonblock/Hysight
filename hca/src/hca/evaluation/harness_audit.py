"""Audit harness for replay and snapshot consistency."""

from __future__ import annotations

from typing import Any, Dict

from hca.common.types import ApprovalGrant
from hca.runtime.replay import reconstruct_state
from hca.runtime.runtime import Runtime
from hca.storage import append_grant, load_latest_valid_snapshot, load_run


def run() -> dict:
    runtime = Runtime()
    run_id = runtime.run("remember to archive this note")
    context = load_run(run_id)
    if context and context.pending_approval_id:
        token = f"audit-{context.pending_approval_id}"
        append_grant(
            run_id,
            ApprovalGrant(
                approval_id=context.pending_approval_id,
                token=token,
                actor="audit",
            ),
        )
        runtime.resume(run_id, context.pending_approval_id, token)

    replay = reconstruct_state(run_id)
    latest_snapshot = load_latest_valid_snapshot(run_id) or {}
    current = load_run(run_id)
    snapshot_state = latest_snapshot.get("state")
    if snapshot_state is not None and hasattr(snapshot_state, "value"):
        snapshot_state = snapshot_state.value

    checks: Dict[str, Any] = {
        "state_matches_context": (
            current is not None
            and replay.get("state") == current.state.value
        ),
        "state_matches_snapshot": replay.get("state") == snapshot_state,
        "selected_action_present": (
            replay.get("selected_action_kind") == "store_note"
        ),
        "no_discrepancies": not replay.get("discrepancies"),
        "memory_recorded": (
            replay.get("memory_counts", {}).get("episodic", 0) >= 1
        ),
    }
    return {
        "harness": "audit",
        "run_id": run_id,
        "state": replay.get("state"),
        "checks": checks,
        "cases": [
            {"name": name, "passed": passed}
            for name, passed in checks.items()
        ],
        "metrics": {
            "audit_pass_rate": len(
                [passed for passed in checks.values() if passed]
            ) / len(checks),
        },
    }
