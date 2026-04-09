import os
import shutil
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
    print(f"DEBUG: replayed state={replayed['state']} approval={replayed['approval']}")
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
    
    append_decision(run_id, ApprovalDecisionRecord(approval_id=app_id, decision=ApprovalDecision.granted))
    append_grant(run_id, ApprovalGrant(approval_id=app_id, token="t1"))
    
    snap_path = f"storage/runs/{run_id}/snapshots.jsonl"
    if os.path.exists(snap_path):
        os.remove(snap_path)
    
    rt.resume(run_id, app_id, "t1")
    
    replayed_final = reconstruct_state(run_id)
    assert replayed_final["state"] == RuntimeState.completed.value
    assert replayed_final["artifacts_count"] == 1

if __name__ == "__main__":
    setup_module()
    test_deny_halts_run()
    print("test_deny_halts_run passed")
    test_resume_from_events_only()
    print("test_resume_from_events_only passed")
