"""Centralized approval validation for execution."""

from datetime import datetime
from typing import Any, Dict, Optional

from hca.common.types import ActionCandidate
from hca.common.time import utc_now
from hca.storage.approvals import (
    get_consumption,
    get_grant,
    get_request,
    resolve_status,
)


def require_approval(action_class: str) -> bool:
    """Determine if an action class requires approval."""
    return action_class in {"medium", "high"}


def _candidate_matches_request(
    candidate: ActionCandidate,
    request: Any,
) -> bool:
    request_binding = getattr(request, "binding", None)
    candidate_binding = candidate.binding

    if request_binding is not None and candidate_binding is not None:
        return request_binding.matches(candidate_binding)

    if request_binding is not None and candidate_binding is None:
        return False

    return request.action_id == candidate.action_id


def validate_resume_approval(
    run_id: str,
    approval_id: str,
    token: str,
    now: Optional[datetime] = None,
    candidate: Optional[ActionCandidate] = None,
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
        request = get_request(run_id, approval_id)
        grant = get_grant(run_id, approval_id)
        if not request:
            result["reason"] = "request_record_missing"
        elif not grant:
            result["reason"] = "grant_record_missing"
        elif (
            grant.binding is not None
            and request.binding is not None
            and not grant.binding.matches(request.binding)
        ):
            result["reason"] = "approval_binding_corrupted"
        elif get_consumption(run_id, approval_id, token=token):
            result["reason"] = "already_consumed"
        elif grant.token != token:
            result["reason"] = "token_mismatch"
        elif candidate is not None and not _candidate_matches_request(
            candidate,
            request,
        ):
            result["reason"] = "approved_action_mismatch"
        else:
            result["ok"] = True

    return result
