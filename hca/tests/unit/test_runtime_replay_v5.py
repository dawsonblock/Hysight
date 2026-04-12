import json
import os
import shutil
from pathlib import Path

import pytest

from hca.runtime.runtime import Runtime
from hca.runtime.replay import reconstruct_state
from hca.common.enums import RuntimeState, ApprovalDecision
from hca.common.types import ApprovalDecisionRecord, ApprovalGrant
from hca.storage.approvals import append_decision, append_grant


def setup_module():
    if os.path.exists("storage/runs"):
        shutil.rmtree("storage/runs")


def test_deny_halts_run():
    rt = Runtime()
    ctx = rt.create_run("buy milk", user_id="u1")
    run_id = ctx.run_id

    rt.deny_approval(run_id, "app-1", reason="too expensive")

    replayed = reconstruct_state(run_id)
    print(
        "DEBUG: replayed "
        f"state={replayed['state']} approval={replayed['approval']}"
    )
    assert replayed["state"] == RuntimeState.halted.value
    assert replayed["approval"] is not None
    assert replayed["approval"]["status"] == "denied"


def test_resume_from_events_only():
    rt = Runtime()
    run_id = rt.run("remember the password")

    replayed = reconstruct_state(run_id)
    assert replayed["state"] == RuntimeState.awaiting_approval.value
    app_id = replayed["pending_approval_id"]
    assert app_id is not None

    assert replayed["selected_action"]["binding"]["action_fingerprint"] == (
        replayed["approval"]["request"]["binding"][
            "action_fingerprint"
        ]
    )

    append_decision(
        run_id,
        ApprovalDecisionRecord(
            approval_id=app_id,
            decision=ApprovalDecision.granted,
        ),
    )
    append_grant(run_id, ApprovalGrant(approval_id=app_id, token="t1"))

    snap_path = f"storage/runs/{run_id}/snapshots.jsonl"
    if os.path.exists(snap_path):
        os.remove(snap_path)

    rt.resume(run_id, app_id, "t1")

    replayed_final = reconstruct_state(run_id)
    assert replayed_final["state"] == RuntimeState.completed.value
    assert replayed_final["artifacts_count"] == 1
    assert replayed_final["discrepancies"] == []
    assert replayed_final["latest_receipt"]["binding"][
        "action_fingerprint"
    ] == replayed_final["selected_action"]["binding"][
        "action_fingerprint"
    ]


def test_resume_rejects_tampered_selected_action():
    rt = Runtime()
    run_id = rt.run("remember the password")

    replayed = reconstruct_state(run_id)
    app_id = replayed["pending_approval_id"]
    assert app_id is not None

    append_decision(
        run_id,
        ApprovalDecisionRecord(
            approval_id=app_id,
            decision=ApprovalDecision.granted,
        ),
    )
    append_grant(run_id, ApprovalGrant(approval_id=app_id, token="t1"))

    events_path = Path(f"storage/runs/{run_id}/events.jsonl")
    events = [
        json.loads(line)
        for line in events_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    for event in reversed(events):
        if event.get("event_type") == "action_selected":
            event["payload"]["arguments"] = {"note": "tampered note"}
            break

    events_path.write_text(
        "\n".join(json.dumps(event) for event in events) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="approved action mismatch"):
        rt.resume(run_id, app_id, "t1")

    replayed_failed = reconstruct_state(run_id)
    assert replayed_failed["state"] == RuntimeState.failed.value
    assert any(
        issue == "Approval request does not match selected action"
        for issue in replayed_failed["discrepancies"]
    )


if __name__ == "__main__":
    setup_module()
    test_deny_halts_run()
    print("test_deny_halts_run passed")
    test_resume_from_events_only()
    print("test_resume_from_events_only passed")
