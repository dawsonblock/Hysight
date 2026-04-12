"""Meta monitoring component for assessing workspace state."""

from __future__ import annotations

from typing import Any, Iterable, List, Optional

from hca.common.enums import ControlSignal
from hca.common.types import (
    CapabilitySummary,
    MetaAssessment,
    RetrievalItem,
    WorkspaceItem,
)
from hca.meta.conflict_detector import detect_conflicts
from hca.meta.missing_info import (
    describe_missing_information,
    detect_missing_information,
)
from hca.meta.self_model import capability_summary


def _iter_retrieval_results(
    workspace_items: List[WorkspaceItem],
    retrieval_results: Optional[Iterable[Any]] = None,
) -> List[RetrievalItem | dict[str, Any]]:
    items: List[RetrievalItem | dict[str, Any]] = []
    if retrieval_results is not None:
        items.extend(list(retrieval_results))
    for workspace_item in workspace_items:
        if workspace_item.kind == "memory_retrieval":
            content = workspace_item.content
            if isinstance(content, list):
                items.extend(content)
    return items


def _retrieval_flags(
    items: List[RetrievalItem | dict[str, Any]],
) -> tuple[list[str], list[str]]:
    contradictions: List[str] = []
    stale: List[str] = []
    for item in items:
        if isinstance(item, RetrievalItem):
            subject = item.record.subject or "unknown"
            is_contradictory = item.contradiction
            staleness = item.staleness
        elif isinstance(item, dict):
            raw_record = item.get("record")
            record = raw_record if isinstance(raw_record, dict) else {}
            subject = record.get("subject") or item.get("subject") or "unknown"
            is_contradictory = item.get(
                "contradiction",
                item.get(
                    "contradiction_status",
                    record.get("contradiction_status", False),
                ),
            )
            staleness = item.get("staleness", record.get("staleness", 0.0))
        else:
            continue

        if is_contradictory:
            contradictions.append(
                f"Contradictory memory for subject: {subject}"
            )
        if staleness > 0.8:
            stale.append(
                f"Stale memory detected for subject {subject} "
                f"(staleness={staleness:.2f})"
            )
    return contradictions, stale


def assess(
    workspace_items: List[WorkspaceItem],
    retrieval_results: Optional[Iterable[Any]] = None,
    failure_count: int = 0,
    capability: Optional[CapabilitySummary] = None,
    proactive_intent_marker: Optional[str] = None,
) -> MetaAssessment:
    """Inspect the workspace and return a meta assessment."""
    conflicts = detect_conflicts(workspace_items)
    missing = detect_missing_information(workspace_items)
    capability = capability or capability_summary(
        workspace_items,
        failure_count=failure_count,
    )
    retrieval_items = _iter_retrieval_results(
        workspace_items,
        retrieval_results=retrieval_results,
    )
    contradiction_flags, stale_flags = _retrieval_flags(retrieval_items)

    actions = [
        item for item in workspace_items if item.kind == "action_suggestion"
    ]
    action_names = [item.content.get("action") for item in actions]
    signal = ControlSignal.proceed
    confidence = 0.9
    explanation = "No anomalies detected. Proceeding."
    reason_code = None
    self_limits = list(stale_flags)

    if failure_count >= 2:
        signal = ControlSignal.halt
        confidence = 0.4
        reason_code = "failure_loop"
        explanation = "Repeated failures detected. Halting."
    elif capability.unsupported_requested_actions:
        signal = ControlSignal.halt
        confidence = 0.5
        reason_code = "unsupported_capability"
        explanation = (
            "Unsupported action requested: "
            f"{', '.join(capability.unsupported_requested_actions)}"
        )
        self_limits.extend(
            f"Action '{action}' is beyond current capabilities."
            for action in capability.unsupported_requested_actions
        )
    elif contradiction_flags:
        signal = ControlSignal.replan
        confidence = 0.5
        reason_code = "memory_contradiction"
        explanation = "; ".join(contradiction_flags)
    elif conflicts:
        signal = ControlSignal.replan
        confidence = 0.55
        reason_code = "conflicting_actions"
        explanation = (
            "Conflicting action suggestions detected: "
            f"{', '.join(conflict.reason_code for conflict in conflicts)}"
        )
        contradiction_flags.extend(
            conflict.reason_code for conflict in conflicts
        )
    elif missing:
        signal = ControlSignal.ask_user
        confidence = 0.7
        reason_code = "missing_required_input"
        explanation = (
            "Action inputs need clarification: "
            + ", ".join(
                describe_missing_information(item)
                for item in missing
            )
        )
    elif stale_flags:
        signal = ControlSignal.ask_user
        confidence = 0.65
        reason_code = "memory_stale"
        explanation = "; ".join(stale_flags)
    elif proactive_intent_marker and any(
        action in {"store_note", "write_artifact"} for action in action_names
    ):
        signal = ControlSignal.require_approval
        confidence = 0.6
        reason_code = "proactive_block"
        explanation = "Proactive write requires explicit approval."
    elif not actions:
        signal = ControlSignal.retrieve_more
        confidence = 0.6
        reason_code = "no_actionable_candidate"
        explanation = "No actionable candidate in workspace."

    return MetaAssessment(
        overall_confidence=confidence,
        contradiction_flags=contradiction_flags,
        missing_information=[
            describe_missing_information(item)
            for item in missing
        ],
        self_limitations=self_limits,
        recommended_transition=signal,
        reason_code=reason_code,
        explanation=explanation,
    )
