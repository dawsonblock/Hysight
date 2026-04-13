# mypy: ignore-errors
# pyright: reportMissingImports=false, reportMissingTypeStubs=false

import json
import os
import shutil

import pytest

import hca.executor.tool_registry as tool_registry
from hca.paths import run_storage_path, storage_root
from hca.runtime.runtime import Runtime
from hca.runtime.replay import reconstruct_state
from hca.common.enums import RuntimeState
from hca.common.types import ApprovalGrant
from hca.storage.approvals import append_grant
from hca.storage.receipts import iter_receipts


def setup_module():
    runs_root = storage_root() / "runs"
    if runs_root.exists():
        shutil.rmtree(runs_root)


def test_deny_halts_run():
    rt = Runtime()
    run_id = rt.run("remember the password", user_id="u1")
    replayed = reconstruct_state(run_id)
    app_id = replayed["pending_approval_id"]
    assert app_id is not None

    rt.deny_approval(run_id, app_id, reason="too expensive")

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

    append_grant(run_id, ApprovalGrant(approval_id=app_id, token="t1"))

    snap_path = run_storage_path(run_id, "snapshots.jsonl")
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

    append_grant(run_id, ApprovalGrant(approval_id=app_id, token="t1"))

    events_path = run_storage_path(run_id, "events.jsonl")
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


def test_resume_patch_action_preserves_binding(monkeypatch, tmp_path):
    monkeypatch.setenv("HCA_STORAGE_ROOT", str(tmp_path / "storage"))
    monkeypatch.setattr(tool_registry, "REPO_ROOT", tmp_path)

    target_path = tmp_path / "notes" / "todo.txt"
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text("hello world\n", encoding="utf-8")

    rt = Runtime()
    run_id = rt.run("replace `world` with `mars` in `notes/todo.txt`")

    replayed = reconstruct_state(run_id)
    assert replayed["state"] == RuntimeState.awaiting_approval.value
    assert replayed["selected_action_kind"] == "patch_text_file"
    app_id = replayed["pending_approval_id"]
    assert app_id is not None
    assert replayed["selected_action"]["binding"]["action_fingerprint"] == (
        replayed["approval"]["request"]["binding"]["action_fingerprint"]
    )

    append_grant(run_id, ApprovalGrant(approval_id=app_id, token="t1"))

    rt.resume(run_id, app_id, "t1")

    replayed_final = reconstruct_state(run_id)
    assert replayed_final["state"] == RuntimeState.completed.value
    patch_receipt = next(
        receipt
        for receipt in iter_receipts(run_id)
        if receipt.get("approval_id") == app_id
        and receipt.get("action_kind") == "patch_text_file"
    )
    assert (
        patch_receipt["binding"]["action_fingerprint"]
        == replayed["approval"]["request"]["binding"][
            "action_fingerprint"
        ]
    )
    assert patch_receipt["side_effects"] == [
        "modified:notes/todo.txt"
    ]
    assert patch_receipt["artifacts"]
    assert target_path.read_text(encoding="utf-8") == "hello mars\n"


def test_workflow_denial_preserves_workflow_context(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("HCA_STORAGE_ROOT", str(tmp_path / "storage"))
    monkeypatch.setattr(tool_registry, "REPO_ROOT", tmp_path)

    target_path = tmp_path / "notes" / "todo.txt"
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text("hello world\n", encoding="utf-8")

    rt = Runtime()
    run_id = rt.run("replace `world` with `mars` in `notes/todo.txt`")

    replayed = reconstruct_state(run_id)
    assert replayed["state"] == RuntimeState.awaiting_approval.value
    assert replayed["active_workflow"]["workflow_class"] == (
        "targeted_mutation"
    )
    app_id = replayed["pending_approval_id"]
    assert app_id is not None

    rt.deny_approval(run_id, app_id, reason="not yet")

    halted = reconstruct_state(run_id)
    assert halted["state"] == RuntimeState.halted.value
    assert halted["approval"] is not None
    assert halted["approval"]["status"] == "denied"
    assert halted["selected_action_kind"] == "patch_text_file"
    assert halted["active_workflow"]["workflow_class"] == (
        "targeted_mutation"
    )
    assert [
        step["step_key"] for step in halted["workflow_step_history"]
    ] == [
        "glob",
        "search",
        "read_context",
        "summary",
        "patch_preview",
    ]
    assert target_path.read_text(encoding="utf-8") == "hello world\n"


if __name__ == "__main__":
    setup_module()
    test_deny_halts_run()
    print("test_deny_halts_run passed")
    test_resume_from_events_only()
    print("test_resume_from_events_only passed")
