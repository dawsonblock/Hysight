import os
import shutil
from hca.common.types import (
    ApprovalConsumption,
    ApprovalDecisionRecord,
    ApprovalGrant,
    ApprovalRequest,
)
from hca.common.enums import ApprovalDecision, ActionClass
from hca.executor.tool_registry import build_action_candidate
from hca.storage.approvals import (
    append_consumption,
    append_decision,
    append_grant,
    append_request,
    get_consumption,
    get_grant,
    resolve_status,
)
from hca.executor.approvals import validate_resume_approval


def setup_module():
    if os.path.exists("storage/runs/test_v5"):
        shutil.rmtree("storage/runs/test_v5")


def test_approval_lifecycle():
    run_id = "test_v5"
    app_id = "app-1"

    candidate = build_action_candidate(
        "store_note",
        {"note": "remember the password"},
    )
    assert candidate.binding is not None

    # 1. Request
    req = ApprovalRequest(
        run_id=run_id,
        approval_id=app_id,
        action_id=candidate.action_id,
        action_kind=candidate.kind,
        action_class=ActionClass.medium,
        binding=candidate.binding,
        reason="test",
    )
    append_request(run_id, req)
    assert resolve_status(run_id, app_id) == "pending"

    # 2. Deny
    dec = ApprovalDecisionRecord(
        approval_id=app_id,
        decision=ApprovalDecision.denied,
        reason="rejected",
    )
    append_decision(run_id, dec)
    assert resolve_status(run_id, app_id) == "denied"

    # 3. Re-decide (Grant) - Multiple decisions resolve to latest
    dec2 = ApprovalDecisionRecord(
        approval_id=app_id,
        decision=ApprovalDecision.granted,
    )
    append_decision(run_id, dec2)
    grant = ApprovalGrant(approval_id=app_id, token="token-123")
    append_grant(run_id, grant)
    assert resolve_status(run_id, app_id) == "granted"

    stored_grant = get_grant(run_id, app_id)
    assert stored_grant is not None
    assert stored_grant.binding is not None
    assert stored_grant.binding.matches(candidate.binding)

    # 4. Validate
    v = validate_resume_approval(
        run_id,
        app_id,
        "token-123",
        candidate=candidate,
    )
    assert v["ok"] is True

    v_wrong = validate_resume_approval(run_id, app_id, "wrong")
    assert v_wrong["ok"] is False
    assert v_wrong["reason"] == "token_mismatch"

    wrong_candidate = build_action_candidate(
        "store_note",
        {"note": "something else"},
    )
    v_wrong_action = validate_resume_approval(
        run_id,
        app_id,
        "token-123",
        candidate=wrong_candidate,
    )
    assert v_wrong_action["ok"] is False
    assert v_wrong_action["reason"] == "approved_action_mismatch"

    # 5. Consume
    cons = ApprovalConsumption(approval_id=app_id, token="token-123")
    append_consumption(run_id, cons)
    assert resolve_status(run_id, app_id) == "consumed"

    stored_consumption = get_consumption(run_id, app_id, token="token-123")
    assert stored_consumption is not None
    assert stored_consumption.binding is not None
    assert stored_consumption.binding.matches(candidate.binding)

    v_cons = validate_resume_approval(run_id, app_id, "token-123")
    assert v_cons["ok"] is False
    assert v_cons["reason"] == "already_consumed"


if __name__ == "__main__":
    setup_module()
    test_approval_lifecycle()
    print("test_approval_lifecycle passed")
