"""Append-only storage helpers for approval requests and decisions."""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

from hca.common.types import (
    ApprovalRequest,
    ApprovalDecisionRecord,
    ApprovalGrant,
    ApprovalConsumption
)
from hca.common.enums import ApprovalDecision
from hca.common.time import parse_iso, utc_now


logger = logging.getLogger(__name__)


def _path(run_id: str) -> Path:
    """Unified path for approval records."""
    return Path(f"storage/runs/{run_id}/approvals.jsonl")


def _append_record(
    run_id: str, record_type: str, payload: Dict[str, Any]
) -> None:
    path = _path(run_id)
    os.makedirs(path.parent, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps({"record_type": record_type, **payload}) + "\n")


def _scan_records(run_id: str) -> Tuple[List[Dict[str, Any]], int]:
    path = _path(run_id)
    if not path.exists():
        return [], 0

    records: List[Dict[str, Any]] = []
    corruption_count = 0
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                corruption_count += 1

    if corruption_count:
        logger.warning(
            "Skipped %s malformed approval record(s) for run %s",
            corruption_count,
            run_id,
        )

    return records, corruption_count


def _latest_model(
    records: List[Dict[str, Any]],
    record_type: str,
    approval_id: str,
    model: Any,
) -> Optional[Any]:
    latest = None
    for record in records:
        if (
            record.get("record_type") == record_type
            and record.get("approval_id") == approval_id
        ):
            latest = model.model_validate(record)
    return latest


def append_request(run_id: str, request: ApprovalRequest) -> None:
    _append_record(run_id, "request", request.model_dump(mode="json"))


def append_decision(run_id: str, decision: ApprovalDecisionRecord) -> None:
    append_decision_record = decision.model_dump(mode="json")
    _append_record(run_id, "decision", append_decision_record)


def append_grant(run_id: str, grant: ApprovalGrant) -> None:
    append_decision(
        run_id,
        ApprovalDecisionRecord(
            approval_id=grant.approval_id,
            decision=ApprovalDecision.granted,
            actor=grant.actor,
            decided_at=grant.granted_at,
            expires_at=grant.expires_at,
        ),
    )
    _append_record(run_id, "grant", grant.model_dump(mode="json"))


def append_denial(
    run_id: str,
    approval_id: str,
    actor: Optional[str] = None,
    decided_at: Optional[datetime] = None,
    expires_at: Optional[datetime] = None,
    reason: Optional[str] = None,
) -> None:
    append_decision(
        run_id,
        ApprovalDecisionRecord(
            approval_id=approval_id,
            decision=ApprovalDecision.denied,
            actor=actor or "user",
            decided_at=decided_at or utc_now(),
            expires_at=expires_at,
            reason=reason,
        ),
    )


def append_consumption(run_id: str, consumption: ApprovalConsumption) -> None:
    _append_record(run_id, "consumption", consumption.model_dump(mode="json"))


def get_corruption_count(run_id: str) -> int:
    _, corruption_count = _scan_records(run_id)
    return corruption_count


def iter_records(run_id: str) -> Iterator[Dict[str, Any]]:
    records, _ = _scan_records(run_id)
    yield from records


def get_request(run_id: str, approval_id: str) -> Optional[ApprovalRequest]:
    records, _ = _scan_records(run_id)
    return _latest_model(records, "request", approval_id, ApprovalRequest)


def get_latest_decision(
    run_id: str, approval_id: str
) -> Optional[ApprovalDecisionRecord]:
    records, _ = _scan_records(run_id)
    return _latest_model(
        records, "decision", approval_id, ApprovalDecisionRecord
    )


def get_grant(run_id: str, approval_id: str) -> Optional[ApprovalGrant]:
    records, _ = _scan_records(run_id)
    return _latest_model(records, "grant", approval_id, ApprovalGrant)


def get_consumption(
    run_id: str,
    approval_id: str,
    token: Optional[str] = None,
) -> Optional[ApprovalConsumption]:
    records, _ = _scan_records(run_id)
    latest = None
    for record in records:
        if (
            record.get("record_type") != "consumption"
            or record.get("approval_id") != approval_id
        ):
            continue
        if token is not None and record.get("token") != token:
            continue
        latest = ApprovalConsumption.model_validate(record)
    return latest


def is_expired(record: Any, now: Optional[datetime] = None) -> bool:
    if record is None:
        return False

    expires_at = None
    if isinstance(record, dict):
        expires_at = record.get("expires_at")
    else:
        expires_at = getattr(record, "expires_at", None)

    if expires_at is None:
        return False

    if isinstance(expires_at, str):
        expires_at = parse_iso(expires_at)

    now = now or utc_now()
    return now > expires_at


def resolve_status(
    run_id: str, approval_id: str, now: Optional[datetime] = None
) -> str:
    """Resolve approval status for an approval request."""
    now = now or utc_now()

    records, _ = _scan_records(run_id)
    req = _latest_model(records, "request", approval_id, ApprovalRequest)
    dec = _latest_model(
        records, "decision", approval_id, ApprovalDecisionRecord
    )
    grant = _latest_model(records, "grant", approval_id, ApprovalGrant)
    consumption = get_consumption(run_id, approval_id)

    if not any([req, dec, grant, consumption]):
        return "missing"

    if dec and dec.decision == ApprovalDecision.denied:
        return "denied"

    if consumption is not None:
        return "consumed"

    if dec and dec.decision == ApprovalDecision.granted:
        expiry_source = grant or dec
        if is_expired(expiry_source, now):
            return "expired"
        return "granted"

    if req and is_expired(req, now):
        return "expired"

    if not dec:
        return "pending"

    return "pending"


def get_approval_status(
    run_id: str, approval_id: str, now: Optional[datetime] = None
) -> Dict[str, Any]:
    now = now or utc_now()
    request = get_request(run_id, approval_id)
    decision = get_latest_decision(run_id, approval_id)
    grant = get_grant(run_id, approval_id)
    consumption = get_consumption(run_id, approval_id)
    status = resolve_status(run_id, approval_id, now=now)
    corruption_count = get_corruption_count(run_id)
    return {
        "approval_id": approval_id,
        "status": status,
        "expired": status == "expired",
        "request": request.model_dump(mode="json") if request else None,
        "decision": decision.model_dump(mode="json") if decision else None,
        "grant": grant.model_dump(mode="json") if grant else None,
        "consumption": (
            consumption.model_dump(mode="json") if consumption else None
        ),
        "corruption_count": corruption_count,
    }


def get_pending_requests(run_id: str) -> List[ApprovalRequest]:
    records, _ = _scan_records(run_id)
    pending = []
    seen_ids = set()
    for record in records:
        if record.get("record_type") == "request":
            aid = record.get("approval_id")
            if isinstance(aid, str) and aid not in seen_ids:
                status = resolve_status(run_id, aid)
                if status == "pending":
                    pending.append(ApprovalRequest.model_validate(record))
                seen_ids.add(aid)
    return pending
