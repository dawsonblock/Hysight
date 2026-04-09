from hca.runtime.runtime import Runtime
from hca.runtime.replay import reconstruct_state
from hca.common.enums import RuntimeState

def test_replay_matches_final_state():
    rt = Runtime()
    # Use a goal that triggers approval and then execution
    run_id = rt.run("remember to buy milk")
    
    # At this point, it's in awaiting_approval
    state_awaiting = reconstruct_state(run_id)
    assert state_awaiting["state"] == RuntimeState.awaiting_approval.value
    assert state_awaiting["pending_approval_id"] is not None
    assert state_awaiting["selected_action_kind"] == "store_note"
    
    # Grant and resume
    from hca.storage.approvals import append_grant, get_pending_requests
    from hca.common.types import ApprovalGrant
    from hca.common.enums import ApprovalDecision
    
    pending = get_pending_requests(run_id)
    approval_id = pending[0].approval_id
    token = "test-token"
    append_grant(run_id, ApprovalGrant(approval_id=approval_id, token=token, decision=ApprovalDecision.granted))
    
    rt.resume(run_id, approval_id, token)
    
    # At this point, it's completed
    state_final = reconstruct_state(run_id)
    assert state_final["state"] == RuntimeState.completed.value
    assert state_final["pending_approval_id"] is None
    # Check if latest_receipt_id exists instead of status
    assert state_final.get("latest_receipt_id") is not None

if __name__ == "__main__":
    test_replay_matches_final_state()
    print("test_replay_matches_final_state passed")
