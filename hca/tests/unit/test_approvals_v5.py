import os
import shutil
from hca.common.types import ApprovalRequest, ApprovalDecisionRecord, ApprovalGrant, ApprovalConsumption
from hca.common.enums import ApprovalDecision, ActionClass
from hca.storage.approvals import append_request, append_decision, append_grant, append_consumption, resolve_status
from hca.executor.approvals import validate_resume_approval

def setup_module():
    if os.path.exists("storage/runs/test_v5"):
        shutil.rmtree("storage/runs/test_v5")

def test_approval_lifecycle():
    run_id = "test_v5"
    app_id = "app-1"
    
    # 1. Request
    req = ApprovalRequest(run_id=run_id, approval_id=app_id, action_id="act-1", action_class=ActionClass.medium, reason="test")
    append_request(run_id, req)
    assert resolve_status(run_id, app_id) == "pending"
    
    # 2. Deny
    dec = ApprovalDecisionRecord(approval_id=app_id, decision=ApprovalDecision.denied, reason="rejected")
    append_decision(run_id, dec)
    assert resolve_status(run_id, app_id) == "denied"
    
    # 3. Re-decide (Grant) - Multiple decisions resolve to latest
    dec2 = ApprovalDecisionRecord(approval_id=app_id, decision=ApprovalDecision.granted)
    append_decision(run_id, dec2)
    grant = ApprovalGrant(approval_id=app_id, token="token-123")
    append_grant(run_id, grant)
    assert resolve_status(run_id, app_id) == "granted"
    
    # 4. Validate
    v = validate_resume_approval(run_id, app_id, "token-123")
    assert v["ok"] is True
    
    v_wrong = validate_resume_approval(run_id, app_id, "wrong")
    assert v_wrong["ok"] is False
    assert v_wrong["reason"] == "token_mismatch"
    
    # 5. Consume
    cons = ApprovalConsumption(approval_id=app_id, token="token-123")
    append_consumption(run_id, cons)
    assert resolve_status(run_id, app_id) == "consumed"
    
    v_cons = validate_resume_approval(run_id, app_id, "token-123")
    assert v_cons["ok"] is False
    assert v_cons["reason"] == "already_consumed"

if __name__ == "__main__":
    setup_module()
    test_approval_lifecycle()
    print("test_approval_lifecycle passed")
