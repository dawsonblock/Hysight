"""Shared runtime action helpers for HTTP adapters and evaluation harnesses."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from hca.runtime.runtime import Runtime
from hca.storage import load_run


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
    context = load_run(run_id)
    if context is None or context.pending_approval_id is None:
        return run_id

    approval_id = context.pending_approval_id
    token = f"{token_prefix}-{approval_id}"
    return grant_pending_approval(
        run_id,
        approval_id,
        token=token,
        actor=actor,
    )
