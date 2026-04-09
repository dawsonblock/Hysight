from hca.runtime.runtime import Runtime
from hca.runtime.replay import reconstruct_state
from hca.common.enums import RuntimeState, ApprovalDecision
from hca.storage.approvals import append_grant, get_pending_requests
from hca.common.types import ApprovalGrant

def test_replay_after_deny():
    rt = Runtime()
    run_id = rt.run("remember something")
    
    pending = get_pending_requests(run_id)
    approval_id = pending[0].approval_id
    
    from hca.storage.approvals import append_denial
    append_denial(run_id, approval_id, reason="User test")
    
    rt.resume(run_id, approval_id, "no-token")
    
    state = reconstruct_state(run_id)
    # print(f"DEBUG: Final state={state['state']} pending={state['pending_approval_id']} decision={state['last_approval_decision']}")
    assert state["state"] == RuntimeState.halted.value
    assert state["last_approval_decision"] == ApprovalDecision.denied.value
    assert state["pending_approval_id"] == approval_id

def test_replay_after_completion():
    rt = Runtime()
    run_id = rt.run("echo hello")
    
    state = reconstruct_state(run_id)
    assert state["state"] == RuntimeState.completed.value
    assert state["selected_action_kind"] == "echo"
    assert state["latest_receipt_id"] is not None
    assert state["memory_counts"]["episodic"] >= 1

if __name__ == "__main__":
    test_replay_after_deny()
    print("test_replay_after_deny passed")
    test_replay_after_completion()
    print("test_replay_after_completion passed")
