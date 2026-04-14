"""Shared runtime action helpers for HTTP adapters and evaluation harnesses."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from hca.runtime.replay import reconstruct_state
from hca.runtime.runtime import Runtime


def run_goal(goal: str, user_id: Optional[str] = None) -> str:
    return Runtime().run(goal, user_id=user_id)


def grant_pending_approval(
    run_id: str,
    approval_id: str,
    *,
    token: str,
    actor: str = "user",
    expires_at: Optional[datetime] = None,
) -> str:
    runtime = Runtime()
    return runtime.grant_approval(
        run_id,
        approval_id,
        token,
        actor=actor,
        expires_at=expires_at,
    )


def deny_pending_approval(
    run_id: str,
    approval_id: str,
    *,
    reason: str = "Denied by user",
) -> str:
    runtime = Runtime()
    return runtime.deny_approval(run_id, approval_id, reason=reason)


def auto_grant_pending_approval(
    run_id: str,
    *,
    actor: str,
    token_prefix: str = "eval",
) -> str:
    """Grant the current approval for evaluation-only harness flows."""

    replay = reconstruct_state(run_id)
    approval = replay.get("approval")
    if not isinstance(approval, dict) or approval.get("status") != "pending":
        return run_id

    approval_id = approval.get("approval_id") or replay.get(
        "pending_approval_id"
    )
    if not isinstance(approval_id, str):
        return run_id

    token = f"{token_prefix}-{uuid.uuid4().hex}"
    return grant_pending_approval(
        run_id,
        approval_id,
        token=token,
        actor=actor,
    )
