"""Shared replay-backed run API models and helpers."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from pydantic import ValidationError

from hca.api.models import (
    RunActionResponse,
    RunArtifactDetailResponse,
    RunArtifactListResponse,
    RunArtifactResponse,
    RunEventListResponse,
    RunEventResponse,
    RunKeyEventResponse,
    RunLatencySummaryResponse,
    RunListResponse,
    RunMemoryHitResponse,
    RunMetricsResponse,
    RunPlanResponse,
    RunResultResponse,
    RunSummaryResponse,
    RunPerceptionResponse,
    RunCritiqueResponse,
    RunWorkflowOutcomeResponse,
)

from hca.paths import (
    ensure_repo_root_on_sys_path,
    run_storage_path,
    storage_root,
)
from hca.runtime.replay import reconstruct_state
from hca.storage import iter_artifacts, iter_events, load_run


ensure_repo_root_on_sys_path()


logger = logging.getLogger(__name__)


_KEY_EVENT_TYPES = {
    "run_created",
    "module_proposed",
    "action_selected",
    "approval_requested",
    "approval_granted",
    "approval_denied",
    "execution_finished",
    "workflow_selected",
    "workflow_step_started",
    "workflow_step_finished",
    "workflow_budget_exhausted",
    "workflow_terminated",
    "run_completed",
    "run_failed",
    "memory_written",
    "episodic_memory_written",
    "external_memory_written",
    "external_memory_write_failed",
}


def require_run_context(run_id: str):
    context = load_run(run_id)
    if not context:
        raise HTTPException(status_code=404, detail="Run not found")
    return context


def require_pending_approval_selection(run_id: str, approval_id: str):
    from hca.storage.approvals import get_request

    context = require_run_context(run_id)
    replay = reconstruct_state(run_id)
    replay_state = str(replay.get("state") or context.state.value)
    approval = replay.get("approval")
    if not isinstance(approval, dict):
        approval = None

    pending_approval_id = None
    if approval is not None and approval.get("status") == "pending":
        candidate_id = approval.get("approval_id")
        if isinstance(candidate_id, str):
            pending_approval_id = candidate_id
    if pending_approval_id is None and replay_state == "awaiting_approval":
        candidate_id = replay.get("pending_approval_id")
        if isinstance(candidate_id, str):
            pending_approval_id = candidate_id

    if (
        replay_state != "awaiting_approval"
        and not (
            context.state.value == "awaiting_approval"
            and pending_approval_id is not None
        )
    ) or pending_approval_id is None:
        raise HTTPException(
            status_code=400,
            detail="Run has no pending approval",
        )
    if pending_approval_id != approval_id:
        raise HTTPException(
            status_code=400,
            detail="Approval id does not match pending approval",
        )
    if get_request(run_id, approval_id) is None:
        raise HTTPException(
            status_code=400,
            detail="Approval request record is missing",
        )
    return context


def event_summary(event_type: str, payload: Dict[str, Any]) -> str:
    approval_label = str(payload.get("approval_id") or "?")[:8]
    mapping = {
        "run_created": "Run started — goal logged",
        "module_proposed": (
            f"Module '{payload.get('source_module', '?')}' proposed "
            f"{len(payload.get('candidate_items', []))} item(s)"
        ),
        "action_selected": f"Selected action: {payload.get('kind', '?')}",
        "approval_requested": (
            "Approval requested "
            f"(id={approval_label}...)"
        ),
        "approval_granted": (
            "Approval granted "
            f"(id={approval_label}...)"
        ),
        "approval_denied": (
            "Approval denied "
            f"(id={approval_label}...)"
        ),
        "execution_finished": f"Execution {payload.get('status', '?')}",
        "workflow_selected": (
            "Workflow selected: "
            f"{payload.get('workflow_class', '?')}"
        ),
        "workflow_step_started": (
            "Workflow step started: "
            f"{payload.get('step_key') or payload.get('tool_name', '?')}"
        ),
        "workflow_step_finished": (
            "Workflow step finished: "
            f"{payload.get('step_key') or payload.get('tool_name', '?')}"
            f" ({payload.get('status', '?')})"
        ),
        "workflow_budget_exhausted": "Workflow budget exhausted",
        "workflow_terminated": (
            "Workflow terminated: "
            f"{payload.get('reason', '?')}"
        ),
        "run_completed": "Run completed successfully",
        "run_failed": "Run failed",
        "memory_written": (
            f"Memory written — subject: {payload.get('subject', '?')}"
        ),
        "episodic_memory_written": "Episodic memory written",
        "external_memory_written": "External memory written",
        "external_memory_write_failed": "External memory write failed",
    }
    return mapping.get(event_type, event_type.replace("_", " "))


def _dict_str_any(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {str(key): item for key, item in value.items()}


def _dict_str_int(value: Any) -> Dict[str, int]:
    if not isinstance(value, dict):
        return {}

    normalized: Dict[str, int] = {}
    for key, item in value.items():
        try:
            normalized[str(key)] = int(item)
        except (TypeError, ValueError):
            continue
    return normalized


def _list_of_dicts(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _list_of_strings(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item is not None]


def _parse_datetime(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value:
        return None

    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _duration_ms(start_value: Any, end_value: Any) -> Optional[float]:
    started_at = _parse_datetime(start_value)
    finished_at = _parse_datetime(end_value)
    if started_at is None or finished_at is None:
        return None

    duration_ms = (finished_at - started_at).total_seconds() * 1000.0
    if duration_ms < 0:
        return None
    return round(duration_ms, 3)


def _latency_summary(samples: List[float]) -> RunLatencySummaryResponse:
    if not samples:
        return RunLatencySummaryResponse()
    return RunLatencySummaryResponse(
        count=len(samples),
        total_ms=round(sum(samples), 3),
        max_ms=round(max(samples), 3),
        last_ms=round(samples[-1], 3),
    )


def _recorded_memory_hits(
    payload: Dict[str, Any],
) -> List[RunMemoryHitResponse]:
    hits: List[RunMemoryHitResponse] = []
    for raw_hit in payload.get("memory_hits", []):
        if not isinstance(raw_hit, dict):
            continue
        try:
            hits.append(RunMemoryHitResponse.model_validate(raw_hit))
        except ValidationError:
            continue
    return hits


def extract_run_summary(run_id: str) -> RunSummaryResponse:
    context = require_run_context(run_id)
    events = list(iter_events(run_id))
    replay = reconstruct_state(run_id)

    plan = RunPlanResponse()
    action_taken = RunActionResponse()
    perception = RunPerceptionResponse()
    critique = RunCritiqueResponse()
    action_result = RunResultResponse()
    approval_id: Optional[str] = replay.get("pending_approval_id")
    key_events: List[RunKeyEventResponse] = []
    memory_hits: List[RunMemoryHitResponse] = []
    tool_latency_samples: List[float] = []
    memory_retrieval_latency_samples: List[float] = []
    memory_commit_latency_samples: List[float] = []

    for event in events:
        event_type = event.get("event_type", "")
        payload = event.get("payload", {})
        safe_payload = payload if isinstance(payload, dict) else {}

        if event_type == "module_proposed" and event.get("actor") == "planner":
            for candidate_item in safe_payload.get("candidate_items", []):
                if candidate_item.get("kind") == "task_plan":
                    content = candidate_item.get("content", {})
                    memory_hits = _recorded_memory_hits(content)
                    retrieval_latency = content.get(
                        "memory_retrieval_latency_ms"
                    )
                    if isinstance(retrieval_latency, (int, float)):
                        memory_retrieval_latency_samples.append(
                            round(float(retrieval_latency), 3)
                        )
                    plan = RunPlanResponse(
                        strategy=content.get("strategy"),
                        action=content.get("action"),
                        rationale=content.get("rationale", ""),
                        confidence=candidate_item.get("confidence", 1.0),
                        memory_context_used=content.get(
                            "memory_context_used",
                            False,
                        ),
                        planning_mode=(
                            str(content.get("planning_mode"))
                            if content.get("planning_mode") is not None
                            else None
                        ),
                        fallback_reason=(
                            str(content.get("fallback_reason"))
                            if content.get("fallback_reason") is not None
                            else None
                        ),
                        memory_retrieval_status=(
                            str(content.get("memory_retrieval_status"))
                            if content.get("memory_retrieval_status")
                            is not None
                            else None
                        ),
                        memory_retrieval_error=(
                            str(content.get("memory_retrieval_error"))
                            if content.get("memory_retrieval_error")
                            is not None
                            else None
                        ),
                    )

        if (
            event_type == "module_proposed"
            and event.get("actor") == "perception_text"
        ):
            for candidate_item in safe_payload.get("candidate_items", []):
                if candidate_item.get("kind") == "perceived_intent":
                    content = candidate_item.get("content", {})
                    perception = RunPerceptionResponse(
                        intent_class=(
                            str(content.get("intent_class"))
                            if content.get("intent_class") is not None
                            else None
                        ),
                        intent=(
                            str(content.get("intent"))
                            if content.get("intent") is not None
                            else None
                        ),
                        perception_mode=(
                            str(content.get("perception_mode"))
                            if content.get("perception_mode") is not None
                            else None
                        ),
                        fallback_reason=(
                            str(content.get("fallback_reason"))
                            if content.get("fallback_reason") is not None
                            else None
                        ),
                        llm_attempted=bool(
                            content.get("llm_attempted", False)
                        ),
                    )

        if event_type == "recurrent_pass_completed":
            for revision_payload in safe_payload.get("revision_payloads", []):
                if not isinstance(revision_payload, dict):
                    continue
                if revision_payload.get("source_module") != "critic":
                    continue
                for critique_item in revision_payload.get(
                    "critique_items",
                    [],
                ):
                    if not isinstance(critique_item, dict):
                        continue
                    if critique_item.get("kind") != "critic_verdict":
                        continue
                    content = critique_item.get("content", {})
                    critique = RunCritiqueResponse(
                        verdict=(
                            str(content.get("verdict"))
                            if content.get("verdict") is not None
                            else None
                        ),
                        alignment=(
                            float(content.get("alignment"))
                            if isinstance(
                                content.get("alignment"),
                                (int, float),
                            )
                            else None
                        ),
                        feasibility=(
                            float(content.get("feasibility"))
                            if isinstance(
                                content.get("feasibility"),
                                (int, float),
                            )
                            else None
                        ),
                        safety=(
                            float(content.get("safety"))
                            if isinstance(
                                content.get("safety"),
                                (int, float),
                            )
                            else None
                        ),
                        issues=_list_of_strings(content.get("issues")),
                        rationale=str(content.get("rationale", "")),
                        llm_powered=bool(
                            content.get("llm_powered", False)
                        ),
                        fallback_reason=(
                            str(content.get("fallback_reason"))
                            if content.get("fallback_reason") is not None
                            else None
                        ),
                        confidence_delta=(
                            float(content.get("confidence_delta"))
                            if isinstance(
                                content.get("confidence_delta"),
                                (int, float),
                            )
                            else None
                        ),
                    )

        if (
            event_type == "action_selected"
            and not replay.get("selected_action")
        ):
            action_taken = RunActionResponse(
                kind=safe_payload.get("kind"),
                arguments=safe_payload.get("arguments", {}),
                action_id=safe_payload.get("action_id"),
                requires_approval=safe_payload.get("requires_approval", False),
            )

        if event_type == "approval_requested" and approval_id is None:
            approval_id = safe_payload.get("approval_id")

        if event_type == "execution_finished":
            if replay.get("latest_receipt") is None:
                action_result = RunResultResponse(
                    status=safe_payload.get("status"),
                    outputs=safe_payload.get("outputs"),
                    artifacts=safe_payload.get("artifacts") or [],
                    error=safe_payload.get("error"),
                )
            duration_ms = _duration_ms(
                safe_payload.get("started_at"),
                safe_payload.get("finished_at"),
            )
            if duration_ms is None:
                outputs = safe_payload.get("outputs")
                if isinstance(outputs, dict) and isinstance(
                    outputs.get("duration_seconds"),
                    (int, float),
                ):
                    duration_ms = round(
                        float(outputs["duration_seconds"]) * 1000.0,
                        3,
                    )
            if duration_ms is not None:
                tool_latency_samples.append(duration_ms)

        if event_type in {
            "episodic_memory_written",
            "external_memory_written",
            "external_memory_write_failed",
        }:
            latency_ms = safe_payload.get("latency_ms")
            if isinstance(latency_ms, (int, float)):
                memory_commit_latency_samples.append(
                    round(float(latency_ms), 3)
                )

        if event_type in _KEY_EVENT_TYPES:
            key_events.append(
                RunKeyEventResponse(
                    type=event_type,
                    actor=event.get("actor"),
                    timestamp=event.get("timestamp"),
                    summary=event_summary(event_type, safe_payload),
                )
            )

    replay_action = replay.get("selected_action")
    if isinstance(replay_action, dict):
        action_taken = RunActionResponse(
            kind=replay_action.get("kind"),
            arguments=replay_action.get("arguments", {}),
            action_id=replay_action.get("action_id"),
            requires_approval=replay_action.get("requires_approval", False),
        )

    latest_receipt = replay.get("latest_receipt")
    if isinstance(latest_receipt, dict):
        action_result = RunResultResponse(
            status=latest_receipt.get("status"),
            outputs=latest_receipt.get("outputs"),
            artifacts=latest_receipt.get("artifacts") or [],
            error=latest_receipt.get("error"),
        )

    active_workflow = replay.get("active_workflow")
    if plan.strategy is None and isinstance(active_workflow, dict):
        plan = RunPlanResponse(
            strategy=active_workflow.get("strategy"),
            action=action_taken.kind,
            rationale=active_workflow.get("rationale", ""),
            confidence=float(active_workflow.get("confidence") or 1.0),
            memory_context_used=bool(memory_hits),
            planning_mode="workflow_chain",
            fallback_reason=None,
        )

    metrics = RunMetricsResponse(
        run_duration_ms=_duration_ms(context.created_at, context.updated_at),
        tool_latency=_latency_summary(tool_latency_samples),
        memory_retrieval_latency=_latency_summary(
            memory_retrieval_latency_samples
        ),
        memory_commit_latency=_latency_summary(memory_commit_latency_samples),
    )

    workflow_outcome = RunWorkflowOutcomeResponse.model_validate(
        replay.get("workflow_outcome")
        if isinstance(replay.get("workflow_outcome"), dict)
        else {}
    )

    return RunSummaryResponse(
        run_id=run_id,
        goal=context.goal,
        state=str(replay.get("state") or context.state.value),
        created_at=context.created_at,
        updated_at=context.updated_at,
        plan=plan,
        perception=perception,
        critique=critique,
        action_taken=action_taken,
        action_result=action_result,
        approval_id=approval_id,
        approval=(
            replay.get("approval")
            if isinstance(replay.get("approval"), dict)
            else None
        ),
        last_approval_decision=(
            str(replay.get("last_approval_decision"))
            if replay.get("last_approval_decision") is not None
            else None
        ),
        latest_receipt=(
            latest_receipt if isinstance(latest_receipt, dict) else None
        ),
        artifacts=_list_of_dicts(replay.get("artifacts")),
        artifacts_count=int(replay.get("artifacts_count") or 0),
        memory_counts=_dict_str_int(replay.get("memory_counts")),
        memory_outcomes=_dict_str_any(replay.get("memory_outcomes")),
        active_workflow=(
            active_workflow if isinstance(active_workflow, dict) else None
        ),
        workflow_budget=(
            replay.get("workflow_budget")
            if isinstance(replay.get("workflow_budget"), dict)
            else None
        ),
        workflow_checkpoint=(
            replay.get("workflow_checkpoint")
            if isinstance(replay.get("workflow_checkpoint"), dict)
            else None
        ),
        workflow_step_history=_list_of_dicts(
            replay.get("workflow_step_history")
        ),
        workflow_artifacts=_list_of_dicts(replay.get("workflow_artifacts")),
        workflow_outcome=workflow_outcome,
        discrepancies=_list_of_strings(replay.get("discrepancies")),
        memory_hits=memory_hits,
        key_events=key_events[-12:],
        event_count=int(replay.get("event_count") or len(events)),
        metrics=metrics,
    )


def iter_run_json_paths() -> List[Path]:
    runs_root = storage_root() / "runs"
    if not runs_root.exists():
        return []
    return sorted(
        (path for path in runs_root.glob("*/run.json") if path.is_file()),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )


def list_run_summaries(
    *,
    limit: int,
    offset: int,
    query_text: Optional[str],
) -> RunListResponse:
    normalized_query = (query_text or "").strip().lower()
    total = 0
    selected_run_ids: List[str] = []

    for run_path in iter_run_json_paths():
        run_id = run_path.parent.name
        context = load_run(run_id)
        if context is None:
            continue

        if normalized_query:
            haystack = f"{run_id} {context.goal}".lower()
            if normalized_query not in haystack:
                continue

        if total >= offset and len(selected_run_ids) < limit:
            selected_run_ids.append(run_id)
        total += 1

    return RunListResponse(
        records=[extract_run_summary(run_id) for run_id in selected_run_ids],
        total=total,
    )


def event_to_response(event: Dict[str, Any]) -> RunEventResponse:
    payload = event.get("payload")
    safe_payload = payload if isinstance(payload, dict) else {}
    event_type = str(event.get("event_type") or "")
    return RunEventResponse(
        event_id=str(event.get("event_id") or ""),
        run_id=str(event.get("run_id") or ""),
        event_type=event_type,
        actor=(
            str(event.get("actor"))
            if event.get("actor") is not None
            else None
        ),
        timestamp=event.get("timestamp"),
        summary=event_summary(event_type, safe_payload),
        payload=safe_payload,
        prior_state=(
            str(event.get("prior_state"))
            if event.get("prior_state") is not None
            else None
        ),
        next_state=(
            str(event.get("next_state"))
            if event.get("next_state") is not None
            else None
        ),
        is_key_event=event_type in _KEY_EVENT_TYPES,
    )


def list_run_events(
    run_id: str,
    *,
    limit: int,
    offset: int,
) -> RunEventListResponse:
    require_run_context(run_id)
    events = list(iter_events(run_id))
    total = len(events)
    selected = list(reversed(events))[offset:offset + limit]
    return RunEventListResponse(
        run_id=run_id,
        records=[event_to_response(event) for event in selected],
        total=total,
    )


def resolve_artifact_full_path(run_id: str, artifact_path: str) -> Path:
    parts = Path(artifact_path).parts
    if len(parts) >= 5 and parts[:4] == (
        "storage",
        "runs",
        run_id,
        "artifacts",
    ):
        candidate = run_storage_path(run_id, "artifacts", *parts[4:])
    else:
        candidate = run_storage_path(run_id, "artifacts", *parts)

    artifacts_root = run_storage_path(run_id, "artifacts").resolve()
    resolved = candidate.resolve()
    if resolved != artifacts_root and artifacts_root not in resolved.parents:
        raise HTTPException(
            status_code=400,
            detail="Artifact path escapes bounded run storage",
        )
    return resolved


def artifact_to_response(record: Dict[str, Any]) -> RunArtifactResponse:
    path = str(record.get("path") or "")
    run_id = str(record.get("run_id") or "")
    content_available = False

    if run_id and path:
        try:
            content_available = resolve_artifact_full_path(
                run_id,
                path,
            ).is_file()
        except HTTPException:
            content_available = False

    metadata = record.get("metadata")
    hashes = record.get("hashes")
    return RunArtifactResponse(
        artifact_id=str(record.get("artifact_id") or ""),
        run_id=run_id,
        action_id=str(record.get("action_id") or ""),
        kind=str(record.get("kind") or ""),
        path=path,
        source_action_ids=[
            str(value)
            for value in record.get("source_action_ids", [])
            if value is not None
        ],
        file_paths=[
            str(value)
            for value in record.get("file_paths", [])
            if value is not None
        ],
        hashes=(
            {
                str(key): str(value)
                for key, value in hashes.items()
                if value is not None
            }
            if isinstance(hashes, dict)
            else {}
        ),
        approval_id=(
            str(record.get("approval_id"))
            if record.get("approval_id") is not None
            else None
        ),
        workflow_id=(
            str(record.get("workflow_id"))
            if record.get("workflow_id") is not None
            else None
        ),
        metadata=metadata if isinstance(metadata, dict) else {},
        created_at=record.get("created_at"),
        content_available=content_available,
    )


def find_artifact_record(run_id: str, artifact_id: str) -> Dict[str, Any]:
    for record in iter_artifacts(run_id):
        if str(record.get("artifact_id")) == artifact_id:
            return record
    raise HTTPException(status_code=404, detail="Artifact not found")


def list_run_artifacts(
    run_id: str,
    *,
    limit: int,
    offset: int,
) -> RunArtifactListResponse:
    require_run_context(run_id)
    artifact_records = list(iter_artifacts(run_id))
    total = len(artifact_records)
    selected = list(reversed(artifact_records))[offset:offset + limit]
    return RunArtifactListResponse(
        run_id=run_id,
        records=[artifact_to_response(record) for record in selected],
        total=total,
    )


def get_run_artifact_detail(
    run_id: str,
    artifact_id: str,
    *,
    preview_bytes: int,
) -> RunArtifactDetailResponse:
    require_run_context(run_id)
    record = find_artifact_record(run_id, artifact_id)
    artifact = artifact_to_response(record)

    if not artifact.content_available:
        raise HTTPException(status_code=404, detail="Artifact content missing")

    artifact_path = resolve_artifact_full_path(run_id, artifact.path)
    raw_content = artifact_path.read_bytes()
    preview = raw_content[:preview_bytes].decode("utf-8", errors="replace")
    return RunArtifactDetailResponse(
        **artifact.model_dump(),
        content=preview,
        size_bytes=len(raw_content),
        truncated=len(raw_content) > preview_bytes,
    )
