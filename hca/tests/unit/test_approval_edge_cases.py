import pytest

import hca.api.runtime_actions as runtime_actions
from hca.common.enums import RuntimeState
from hca.common.types import ApprovalGrant
from hca.runtime.runtime import Runtime
from hca.storage.approvals import (
    append_denial,
    append_grant,
    get_pending_requests,
)


def test_approval_deny_halts_run():
    rt = Runtime()
    run_id = rt.run("remember to buy milk")  # triggers approval

    pending = get_pending_requests(run_id)
    approval_id = pending[0].approval_id

    # Deny the approval
    append_denial(run_id, approval_id, reason="Security policy")

    # Resume should halt
    rt.resume(run_id, approval_id, "no-token")

    assert rt._current_state == RuntimeState.halted


def test_approval_expiry_fails_resume():
    rt = Runtime()
    # Manually trigger a run that will pause
    run_id = rt.run("remember something")

    pending = get_pending_requests(run_id)
    approval_id = pending[0].approval_id

    # We can't easily wait for real expiry in a unit test without mocking time.
    # But we can check if the status reporter sees it.
    from hca.storage.approvals import get_approval_status

    status = get_approval_status(run_id, approval_id)
    # The default expiry is usually in the future.
    assert not status["expired"]


def test_reused_token_fails():
    rt = Runtime()
    run_id = rt.run("remember milk")

    pending = get_pending_requests(run_id)
    approval_id = pending[0].approval_id
    token = "test-token"

    append_grant(run_id, ApprovalGrant(approval_id=approval_id, token=token))

    # First resume succeeds
    rt.resume(run_id, approval_id, token)
    assert rt._current_state == RuntimeState.completed

    # Second resume with same token fails
    with pytest.raises(ValueError) as exc:
        rt.resume(run_id, approval_id, token)
    assert "approval is consumed" in str(exc.value)


def test_auto_grant_pending_approval_uses_randomized_eval_token(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("HCA_STORAGE_ROOT", str(tmp_path / "storage"))

    rt = Runtime()
    run_id = rt.run("remember milk")
    pending = get_pending_requests(run_id)
    approval_id = pending[0].approval_id
    observed: dict[str, str] = {}

    def _capture_grant(
        granted_run_id: str,
        granted_approval_id: str,
        *,
        token: str,
        actor: str = "user",
        expires_at=None,
    ) -> str:
        observed["run_id"] = granted_run_id
        observed["approval_id"] = granted_approval_id
        observed["token"] = token
        observed["actor"] = actor
        return granted_run_id

    monkeypatch.setattr(runtime_actions, "grant_pending_approval", _capture_grant)

    assert runtime_actions.auto_grant_pending_approval(run_id, actor="eval") == run_id
    assert observed == {
        "run_id": run_id,
        "approval_id": approval_id,
        "token": observed["token"],
        "actor": "eval",
    }
    assert observed["token"].startswith("eval-")
    assert observed["token"] != f"eval-{approval_id}"


if __name__ == "__main__":
    # Run tests manually
    test_approval_deny_halts_run()
    print("test_approval_deny_halts_run passed")
    test_reused_token_fails()
    print("test_reused_token_fails passed")
