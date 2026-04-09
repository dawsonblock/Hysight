import uuid
from hca.runtime.runtime import Runtime
from hca.common.enums import RuntimeState, ApprovalDecision
from hca.storage.approvals import get_pending_requests, append_grant
from hca.common.types import ApprovalGrant

def test_approval_flow():
    runtime = Runtime()
    # "store_note" triggers approval in the current stub logic
    run_id = runtime.run("store_note: Hello World")
    
    # Check that the run is paused
    from hca.storage.runs import load_run
    context = load_run(run_id)
    # The run() method returns the run_id when it pauses or completes.
    # We need to check the latest state from the event log or snapshots.
    from hca.storage.snapshots import load_latest_snapshot
    snapshot = load_latest_snapshot(run_id)
    assert snapshot["state"] == RuntimeState.awaiting_approval
    
    # Get pending approval
    pending = get_pending_requests(run_id)
    assert len(pending) == 1
    approval_id = pending[0].approval_id
    
    # Grant approval
    token = str(uuid.uuid4())
    grant = ApprovalGrant(
        approval_id=approval_id,
        token=token,
        decision=ApprovalDecision.granted
    )
    append_grant(run_id, grant)
    
    # Resume run
    runtime.resume(run_id, approval_id, token)
    
    # Check that the run is completed
    snapshot = load_latest_snapshot(run_id)
    assert snapshot["state"] == RuntimeState.completed

if __name__ == "__main__":
    test_approval_flow()
    print("Approval flow test passed!")
