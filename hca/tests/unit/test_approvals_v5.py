import pytest

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


def test_approval_lifecycle(monkeypatch, tmp_path):
    monkeypatch.setenv("HCA_STORAGE_ROOT", str(tmp_path / "storage"))

    run_id = "test_v5"
    denied_approval_id = "app-1"
    granted_approval_id = "app-2"

    candidate = build_action_candidate(
        "store_note",
        {"note": "remember the password"},
    )
    assert candidate.binding is not None

    # 1. Request
    req = ApprovalRequest(
        run_id=run_id,
        approval_id=denied_approval_id,
        action_id=candidate.action_id,
        action_kind=candidate.kind,
        action_class=ActionClass.medium,
        binding=candidate.binding,
        reason="test",
    )
    append_request(run_id, req)
    assert resolve_status(run_id, denied_approval_id) == "pending"

    # 2. Deny
    dec = ApprovalDecisionRecord(
        approval_id=denied_approval_id,
        decision=ApprovalDecision.denied,
        reason="rejected",
    )
    append_decision(run_id, dec)
    assert resolve_status(run_id, denied_approval_id) == "denied"

    # 3. A denied approval id stays terminal; a new approval request is needed.
    with pytest.raises(ValueError, match="approval already denied"):
        append_grant(
            run_id,
            ApprovalGrant(
                approval_id=denied_approval_id,
                token="denied-token",
            ),
        )

    req2 = ApprovalRequest(
        run_id=run_id,
        approval_id=granted_approval_id,
        action_id=candidate.action_id,
        action_kind=candidate.kind,
        action_class=ActionClass.medium,
        binding=candidate.binding,
        reason="retry",
    )
    append_request(run_id, req2)

    grant = ApprovalGrant(
        approval_id=granted_approval_id,
        token="token-123",
    )
    append_grant(run_id, grant)
    assert resolve_status(run_id, granted_approval_id) == "granted"

    stored_grant = get_grant(run_id, granted_approval_id)
    assert stored_grant is not None
    assert stored_grant.binding is not None
    assert stored_grant.binding.matches(candidate.binding)

    # 4. Validate
    v = validate_resume_approval(
        run_id,
        granted_approval_id,
        "token-123",
        candidate=candidate,
    )
    assert v["ok"] is True

    v_wrong = validate_resume_approval(run_id, granted_approval_id, "wrong")
    assert v_wrong["ok"] is False
    assert v_wrong["reason"] == "token_mismatch"

    wrong_candidate = build_action_candidate(
        "store_note",
        {"note": "something else"},
    )
    v_wrong_action = validate_resume_approval(
        run_id,
        granted_approval_id,
        "token-123",
        candidate=wrong_candidate,
    )
    assert v_wrong_action["ok"] is False
    assert v_wrong_action["reason"] == "approved_action_mismatch"

    # 5. Consume
    cons = ApprovalConsumption(
        approval_id=granted_approval_id,
        token="token-123",
    )
    append_consumption(run_id, cons)
    assert resolve_status(run_id, granted_approval_id) == "consumed"

    stored_consumption = get_consumption(
        run_id,
        granted_approval_id,
        token="token-123",
    )
    assert stored_consumption is not None
    assert stored_consumption.binding is not None
    assert stored_consumption.binding.matches(candidate.binding)

    v_cons = validate_resume_approval(
        run_id,
        granted_approval_id,
        "token-123",
    )
    assert v_cons["ok"] is False
    assert v_cons["reason"] == "already_consumed"


if __name__ == "__main__":
    raise SystemExit("Run this module with pytest")
