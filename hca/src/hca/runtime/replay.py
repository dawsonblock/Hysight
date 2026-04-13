"""Richer state reconstruction from event logs and snapshots."""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Optional

from hca.common.enums import EventType, RuntimeState
from hca.executor.tool_registry import (
    ToolValidationError,
    build_action_binding,
)
from hca.runtime.snapshots import (
    count_memory_records,
    summarize_workspace_items,
)
from hca.storage import load_run
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


def _action_fingerprint(payload: Optional[Dict[str, Any]]) -> Optional[str]:
    if not isinstance(payload, dict):
        return None

    binding = payload.get("binding")
    if not isinstance(binding, dict):
        return None

    fingerprint = binding.get("action_fingerprint")
    if isinstance(fingerprint, str):
        return fingerprint
    return None


def _recomputed_action_fingerprint(
    payload: Optional[Dict[str, Any]],
) -> Optional[str]:
    if not isinstance(payload, dict):
        return None

    kind = payload.get("kind")
    if not isinstance(kind, str) or not kind:
        return None

    arguments = payload.get("arguments")
    if not isinstance(arguments, dict):
        arguments = {}

    target = payload.get("target")
    if not isinstance(target, str):
        target = None

    try:
        return build_action_binding(
            kind,
            arguments,
            target=target,
        ).action_fingerprint
    except (KeyError, ToolValidationError):
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


def _memory_outcomes_from_events(
    events: List[Dict[str, Any]],
) -> Dict[str, Any]:
    episodic_writes = 0
    external_writes = 0
    episodic_details: List[Dict[str, Any]] = []
    external_details: List[Dict[str, Any]] = []
    external_failures: List[Dict[str, Any]] = []

    for event in events:
        event_type = event.get("event_type")
        payload = event.get("payload")
        if event_type == EventType.episodic_memory_written.value:
            episodic_writes += 1
            if isinstance(payload, dict):
                episodic_details.append(payload)
        elif event_type == EventType.external_memory_written.value:
            external_writes += 1
            if isinstance(payload, dict):
                external_details.append(payload)
        elif (
            event_type == EventType.external_memory_write_failed.value
            and isinstance(payload, dict)
        ):
            external_failures.append(payload)

    return {
        "episodic_memory_writes": episodic_writes,
        "episodic_memory_details": episodic_details,
        "external_memory_writes": external_writes,
        "external_memory_details": external_details,
        "external_memory_failures": len(external_failures),
        "external_memory_failure_details": external_failures,
    }


def _workflow_outcome_from_events(
    events: List[Dict[str, Any]],
) -> Dict[str, Optional[str]]:
    outcome: Dict[str, Optional[str]] = {
        "terminal_event": None,
        "reason": None,
        "workflow_step_id": None,
        "next_step_id": None,
    }

    for event in events:
        event_type = event.get("event_type")
        payload = event.get("payload")
        safe_payload = payload if isinstance(payload, dict) else {}

        if event_type == EventType.workflow_budget_exhausted.value:
            outcome = {
                "terminal_event": EventType.workflow_budget_exhausted.value,
                "reason": "budget_exhausted",
                "workflow_step_id": None,
                "next_step_id": (
                    str(safe_payload.get("next_step_id"))
                    if safe_payload.get("next_step_id") is not None
                    else None
                ),
            }
        elif event_type == EventType.workflow_terminated.value:
            outcome = {
                "terminal_event": EventType.workflow_terminated.value,
                "reason": (
                    str(safe_payload.get("reason"))
                    if safe_payload.get("reason") is not None
                    else None
                ),
                "workflow_step_id": (
                    str(safe_payload.get("workflow_step_id"))
                    if safe_payload.get("workflow_step_id") is not None
                    else None
                ),
                "next_step_id": (
                    str(safe_payload.get("next_step_id"))
                    if safe_payload.get("next_step_id") is not None
                    else None
                ),
            }

    return outcome


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

    snapshot_action_fingerprint = _action_fingerprint(snapshot_action)
    reconstructed_action_fingerprint = _action_fingerprint(
        reconstructed_action
    )
    if (
        snapshot_action_fingerprint
        and reconstructed_action_fingerprint
        and snapshot_action_fingerprint != reconstructed_action_fingerprint
    ):
        discrepancies.append(
            "Selected action fingerprint mismatch: "
            f"snapshot={snapshot_action_fingerprint}, "
            f"events={reconstructed_action_fingerprint}"
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


def _detect_binding_discrepancies(
    reconstructed: Dict[str, Any],
) -> List[str]:
    discrepancies: List[str] = []
    selected_action = reconstructed.get("selected_action")
    selected_fingerprint = _recomputed_action_fingerprint(selected_action)
    stored_selected_fingerprint = _action_fingerprint(selected_action)
    if (
        selected_fingerprint
        and stored_selected_fingerprint
        and selected_fingerprint != stored_selected_fingerprint
    ):
        discrepancies.append(
            "Selected action binding does not match selected action arguments"
        )
    if selected_fingerprint is None:
        selected_fingerprint = stored_selected_fingerprint

    approval = reconstructed.get("approval")
    if isinstance(approval, dict):
        request_fingerprint = _action_fingerprint(approval.get("request"))
        grant_fingerprint = _action_fingerprint(approval.get("grant"))
        consumption_fingerprint = _action_fingerprint(
            approval.get("consumption")
        )

        if (
            selected_fingerprint
            and request_fingerprint
            and selected_fingerprint != request_fingerprint
        ):
            discrepancies.append(
                "Approval request does not match selected action"
            )

        if (
            request_fingerprint
            and grant_fingerprint
            and request_fingerprint != grant_fingerprint
        ):
            discrepancies.append(
                "Approval grant does not match the original request"
            )

        if (
            request_fingerprint
            and consumption_fingerprint
            and request_fingerprint != consumption_fingerprint
        ):
            discrepancies.append(
                "Approval consumption does not match the original request"
            )

    receipt_fingerprint = _action_fingerprint(
        reconstructed.get("latest_receipt")
    )
    if (
        selected_fingerprint
        and receipt_fingerprint
        and selected_fingerprint != receipt_fingerprint
    ):
        discrepancies.append(
            "Latest receipt does not match selected action"
        )

    return discrepancies


def reconstruct_state(run_id: str) -> Dict[str, Any]:
    """Reconstruct the run state using events as source of truth."""
    events = list(iter_events(run_id))
    snapshot = load_latest_valid_snapshot(run_id)
    context = load_run(run_id)
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
        "memory_outcomes": _memory_outcomes_from_events(events),
        "event_count": len(events),
        "meta_signals_seen": meta_signals_seen,
        "active_workflow": (
            context.active_workflow.model_dump(mode="json")
            if context is not None and context.active_workflow is not None
            else (
                snapshot.get("active_workflow")
                if isinstance(snapshot, dict)
                else None
            )
        ),
        "workflow_budget": (
            context.workflow_budget.model_dump(mode="json")
            if context is not None and context.workflow_budget is not None
            else (
                snapshot.get("workflow_budget")
                if isinstance(snapshot, dict)
                else None
            )
        ),
        "workflow_checkpoint": (
            context.workflow_checkpoint.model_dump(mode="json")
            if context is not None and context.workflow_checkpoint is not None
            else (
                snapshot.get("workflow_checkpoint")
                if isinstance(snapshot, dict)
                else None
            )
        ),
        "workflow_step_history": (
            [
                record.model_dump(mode="json")
                for record in context.workflow_step_history
            ]
            if context is not None
            else (
                snapshot.get("workflow_step_history")
                if isinstance(snapshot, dict)
                else []
            )
        ),
        "workflow_artifacts": (
            [
                artifact.model_dump(mode="json")
                for artifact in context.workflow_artifacts
            ]
            if context is not None
            else (
                snapshot.get("workflow_artifacts")
                if isinstance(snapshot, dict)
                else []
            )
        ),
        "workflow_outcome": _workflow_outcome_from_events(events),
        "discrepancies": [],
    }
    discrepancies = _detect_snapshot_discrepancies(
        snapshot, reconstructed
    )
    discrepancies.extend(_detect_binding_discrepancies(reconstructed))
    reconstructed["discrepancies"] = discrepancies
    return reconstructed
