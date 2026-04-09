"""Centralized approval validation for execution."""

from datetime import datetime
from typing import Any, Dict, Optional

from hca.common.time import utc_now
from hca.storage.approvals import get_consumption, get_grant, resolve_status


def require_approval(action_class: str) -> bool:
    """Determine if an action class requires approval."""
    return action_class in {"medium", "high"}


def validate_resume_approval(
    run_id: str,
    approval_id: str,
    token: str,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Validate if an approval is valid for resumption."""
    now = now or utc_now()
    resolved_status = resolve_status(run_id, approval_id, now)

    result = {
        "ok": False,
        "reason": None,
        "resolved_status": resolved_status,
        "status": resolved_status,
    }

    if resolved_status == "missing":
        result["reason"] = "missing_approval"
    elif resolved_status == "denied":
        result["reason"] = "denied_approval"
    elif resolved_status == "expired":
        result["reason"] = "expired_approval"
    elif resolved_status == "consumed":
        result["reason"] = "already_consumed"
    elif resolved_status == "pending":
        result["reason"] = "pending_approval"
    elif resolved_status == "granted":
        grant = get_grant(run_id, approval_id)
        if not grant:
            result["reason"] = "grant_record_missing"
        elif get_consumption(run_id, approval_id, token=token):
            result["reason"] = "already_consumed"
        elif grant.token != token:
            result["reason"] = "token_mismatch"
        else:
            result["ok"] = True

    return result
