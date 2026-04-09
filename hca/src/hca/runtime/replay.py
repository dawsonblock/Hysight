"""Richer state reconstruction from event logs and snapshots."""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Optional

from hca.common.enums import EventType, RuntimeState
from hca.runtime.snapshots import (
    count_memory_records,
    summarize_workspace_items,
)
from hca.storage.approvals import (
    get_approval_status,
    get_consumption,
    get_grant,
    get_latest_decision,
    get_request,
    iter_records,
)
from hca.storage.artifacts import iter_artifacts
from hca.storage.event_log import iter_events
from hca.storage.receipts import iter_receipts
from hca.storage.snapshots import load_latest_valid_snapshot


def _transition_history(events: List[Dict[str, Any]]) -> List[str]:
    history: List[str] = []
    for event in events:
        if event.get("event_type") == EventType.state_transition.value:
            next_state = event.get("next_state")
            if isinstance(next_state, str):
                history.append(next_state)
    return history


def _selected_action_from_events(
    events: List[Dict[str, Any]],
    snapshot: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    for event in reversed(events):
        if event.get("event_type") == EventType.action_selected.value:
            payload = event.get("payload")
            if isinstance(payload, dict):
                return payload
    if snapshot:
        action = snapshot.get("selected_action")
        if isinstance(action, dict):
            return action
    return None


def _workspace_summary_from_events(
    events: List[Dict[str, Any]],
    snapshot: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    admitted_kinds: Counter[str] = Counter()
    admitted_count = 0
    for event in events:
        if event.get("event_type") != EventType.workspace_admitted.value:
            continue
        payload = event.get("payload", {})
        kind = payload.get("kind")
        if isinstance(kind, str):
            admitted_kinds[kind] += 1
            admitted_count += 1

    if admitted_count:
        return {"item_count": admitted_count, "kinds": dict(admitted_kinds)}

    if snapshot:
        summary = snapshot.get("workspace_summary")
        if isinstance(summary, dict) and summary:
            return summary
        workspace = snapshot.get("workspace")
        if isinstance(workspace, list):
            return summarize_workspace_items(workspace)

    return {"item_count": 0, "kinds": {}}


def _latest_approval_id(
    events: List[Dict[str, Any]],
) -> Optional[str]:
    for event in reversed(events):
        payload = event.get("payload", {})
        approval_id = payload.get("approval_id")
        if isinstance(approval_id, str):
            return approval_id
    return None


def _approval_summary(
    run_id: str,
    approval_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    target = approval_id
    if target is None:
        for record in iter_records(run_id):
            candidate = record.get("approval_id")
            if isinstance(candidate, str):
                target = candidate
    if target is None:
        return None

    status = get_approval_status(run_id, target)
    request = get_request(run_id, target)
    decision = get_latest_decision(run_id, target)
    grant = get_grant(run_id, target)
    consumption = get_consumption(run_id, target)
    status["request"] = (
        request.model_dump(mode="json") if request else None
    )
    status["decision"] = (
        decision.model_dump(mode="json") if decision else None
    )
    status["grant"] = grant.model_dump(mode="json") if grant else None
    status["consumption"] = (
        consumption.model_dump(mode="json") if consumption else None
    )
    return status


def _memory_counts(run_id: str) -> Dict[str, int]:
    return count_memory_records(run_id)


def _detect_snapshot_discrepancies(
    snapshot: Optional[Dict[str, Any]],
    reconstructed: Dict[str, Any],
) -> List[str]:
    if not snapshot:
        return []

    discrepancies: List[str] = []
    snapshot_state = snapshot.get("state")
    if snapshot_state and snapshot_state != reconstructed["state"]:
        discrepancies.append(
            f"State mismatch: snapshot={snapshot_state}, "
            f"events={reconstructed['state']}"
        )

    snapshot_pending = snapshot.get("pending_approval_id") or snapshot.get(
        "pending_approval"
    )
    if snapshot_pending != reconstructed["pending_approval_id"]:
        discrepancies.append(
            "Pending approval mismatch: "
            f"snapshot={snapshot_pending}, "
            f"events={reconstructed['pending_approval_id']}"
        )

    snapshot_action = snapshot.get("selected_action")
    reconstructed_action = reconstructed["selected_action"]
    snapshot_action_id = (
        snapshot_action.get("action_id")
        if isinstance(snapshot_action, dict)
        else None
    )
    reconstructed_action_id = (
        reconstructed_action.get("action_id")
        if isinstance(reconstructed_action, dict)
        else None
    )
    if snapshot_action_id and snapshot_action_id != reconstructed_action_id:
        discrepancies.append(
            "Selected action mismatch: "
            f"snapshot={snapshot_action_id}, "
            f"events={reconstructed_action_id}"
        )

    snapshot_memory = snapshot.get("memory_summary", {})
    if isinstance(snapshot_memory, dict):
        for key, value in snapshot_memory.items():
            if reconstructed["memory_counts"].get(key) != value:
                discrepancies.append(
                    f"Memory mismatch ({key}): snapshot={value}, "
                    f"events={reconstructed['memory_counts'].get(key)}"
                )

    return discrepancies


def reconstruct_state(run_id: str) -> Dict[str, Any]:
    """Reconstruct the run state using events as source of truth."""
    events = list(iter_events(run_id))
    snapshot = load_latest_valid_snapshot(run_id)
    history = _transition_history(events)
    selected_action = _selected_action_from_events(events, snapshot=snapshot)
    workspace_summary = _workspace_summary_from_events(
        events, snapshot=snapshot
    )

    pending_approval_id = None
    meta_signals_seen: List[str] = []
    for event in events:
        event_type = event.get("event_type")
        payload = event.get("payload", {})
        if event_type == EventType.approval_requested.value:
            approval_id = payload.get("approval_id")
            if isinstance(approval_id, str):
                pending_approval_id = approval_id
        elif event_type == EventType.execution_finished.value:
            pending_approval_id = None
        elif event_type == EventType.meta_assessed.value:
            signal = payload.get("recommended_transition")
            if isinstance(signal, str):
                meta_signals_seen.append(signal)

    latest_receipt = None
    for receipt in iter_receipts(run_id):
        latest_receipt = receipt

    artifacts = list(iter_artifacts(run_id))
    approval = _approval_summary(
        run_id,
        approval_id=pending_approval_id or _latest_approval_id(events),
    )
    if (
        approval
        and pending_approval_id is None
        and approval["status"] == "denied"
    ):
        pending_approval_id = approval["approval_id"]

    reconstructed_state = RuntimeState.created.value
    if history:
        reconstructed_state = history[-1]
    elif snapshot:
        reconstructed_state = snapshot.get("state", RuntimeState.created.value)

    reconstructed = {
        "run_id": run_id,
        "state": reconstructed_state,
        "transition_history": history,
        "selected_action": selected_action,
        "selected_action_kind": (
            selected_action.get("kind")
            if isinstance(selected_action, dict)
            else None
        ),
        "workspace_summary": workspace_summary,
        "pending_approval_id": pending_approval_id,
        "approval": approval,
        "last_approval_decision": (
            approval["decision"]["decision"]
            if approval and isinstance(approval.get("decision"), dict)
            else None
        ),
        "latest_receipt": latest_receipt,
        "latest_receipt_id": (
            latest_receipt.get("receipt_id") if latest_receipt else None
        ),
        "artifacts": artifacts,
        "artifacts_count": len(artifacts),
        "memory_counts": _memory_counts(run_id),
        "event_count": len(events),
        "meta_signals_seen": meta_signals_seen,
        "discrepancies": [],
    }
    reconstructed["discrepancies"] = _detect_snapshot_discrepancies(
        snapshot, reconstructed
    )
    return reconstructed
