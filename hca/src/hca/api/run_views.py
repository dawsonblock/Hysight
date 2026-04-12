"""Shared replay-backed run API models and helpers."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field

from hca.paths import (
    ensure_repo_root_on_sys_path,
    run_storage_path,
    storage_root,
)
from hca.runtime.replay import reconstruct_state
from hca.storage import iter_artifacts, iter_events, load_run


ensure_repo_root_on_sys_path()

_retrieval_query_cls: Any = None
_memory_configuration_error: type[Exception] = RuntimeError
_memory_backend_error: type[Exception] = RuntimeError

try:
    from memory_service import RetrievalQuery as _imported_retrieval_query
    from memory_service.config import (
        MemoryConfigurationError as _imported_configuration_error,
    )
    from memory_service.controller import (
        MemoryBackendError as _imported_backend_error,
    )

    _retrieval_query_cls = _imported_retrieval_query
    _memory_configuration_error = _imported_configuration_error
    _memory_backend_error = _imported_backend_error
except ImportError:  # pragma: no cover - package layout fallback
    pass


logger = logging.getLogger(__name__)


class RunAPIModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RunPlanResponse(RunAPIModel):
    strategy: Optional[str] = None
    action: Optional[str] = None
    rationale: str = ""
    confidence: float = 1.0
    memory_context_used: bool = False


class RunActionResponse(RunAPIModel):
    kind: Optional[str] = None
    arguments: Dict[str, Any] = Field(default_factory=dict)
    action_id: Optional[str] = None
    requires_approval: bool = False


class RunResultResponse(RunAPIModel):
    status: Optional[str] = None
    outputs: Optional[Dict[str, Any]] = None
    artifacts: List[str] = Field(default_factory=list)
    error: Optional[str] = None


class RunMemoryHitResponse(RunAPIModel):
    text: str
    score: float
    memory_type: Optional[str] = None
    stored_at: Optional[datetime] = None


class RunKeyEventResponse(RunAPIModel):
    type: str
    actor: Optional[str] = None
    timestamp: Optional[datetime] = None
    summary: str


class RunSummaryResponse(RunAPIModel):
    run_id: str
    goal: str
    state: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    plan: RunPlanResponse = Field(default_factory=RunPlanResponse)
    action_taken: RunActionResponse = Field(default_factory=RunActionResponse)
    action_result: RunResultResponse = Field(default_factory=RunResultResponse)
    approval_id: Optional[str] = None
    approval: Optional[Dict[str, Any]] = None
    last_approval_decision: Optional[str] = None
    latest_receipt: Optional[Dict[str, Any]] = None
    artifacts: List[Dict[str, Any]] = Field(default_factory=list)
    artifacts_count: int = 0
    memory_counts: Dict[str, int] = Field(default_factory=dict)
    memory_outcomes: Dict[str, Any] = Field(default_factory=dict)
    active_workflow: Optional[Dict[str, Any]] = None
    workflow_budget: Optional[Dict[str, Any]] = None
    workflow_checkpoint: Optional[Dict[str, Any]] = None
    workflow_step_history: List[Dict[str, Any]] = Field(default_factory=list)
    workflow_artifacts: List[Dict[str, Any]] = Field(default_factory=list)
    discrepancies: List[str] = Field(default_factory=list)
    memory_hits: List[RunMemoryHitResponse] = Field(default_factory=list)
    key_events: List[RunKeyEventResponse] = Field(default_factory=list)
    event_count: int = 0


class RunListResponse(RunAPIModel):
    records: List[RunSummaryResponse] = Field(default_factory=list)
    total: int = 0


class RunEventResponse(RunAPIModel):
    event_id: str
    run_id: str
    event_type: str
    actor: Optional[str] = None
    timestamp: Optional[datetime] = None
    summary: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    prior_state: Optional[str] = None
    next_state: Optional[str] = None
    is_key_event: bool = False


class RunEventListResponse(RunAPIModel):
    run_id: str
    records: List[RunEventResponse] = Field(default_factory=list)
    total: int = 0


class RunArtifactResponse(RunAPIModel):
    artifact_id: str
    run_id: str
    action_id: str
    kind: str
    path: str
    source_action_ids: List[str] = Field(default_factory=list)
    file_paths: List[str] = Field(default_factory=list)
    hashes: Dict[str, str] = Field(default_factory=dict)
    approval_id: Optional[str] = None
    workflow_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None
    content_available: bool = False


class RunArtifactListResponse(RunAPIModel):
    run_id: str
    records: List[RunArtifactResponse] = Field(default_factory=list)
    total: int = 0


class RunArtifactDetailResponse(RunArtifactResponse):
    content: Optional[str] = None
    size_bytes: int = 0
    truncated: bool = False


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


def extract_run_summary(run_id: str) -> RunSummaryResponse:
    context = require_run_context(run_id)
    events = list(iter_events(run_id))
    replay = reconstruct_state(run_id)

    plan = RunPlanResponse()
    action_taken = RunActionResponse()
    action_result = RunResultResponse()
    approval_id: Optional[str] = replay.get("pending_approval_id")
    key_events: List[RunKeyEventResponse] = []

    for event in events:
        event_type = event.get("event_type", "")
        payload = event.get("payload", {})

        if event_type == "module_proposed" and event.get("actor") == "planner":
            for candidate_item in payload.get("candidate_items", []):
                if candidate_item.get("kind") == "task_plan":
                    content = candidate_item.get("content", {})
                    plan = RunPlanResponse(
                        strategy=content.get("strategy"),
                        action=content.get("action"),
                        rationale=content.get("rationale", ""),
                        confidence=candidate_item.get("confidence", 1.0),
                        memory_context_used=content.get(
                            "memory_context_used",
                            False,
                        ),
                    )

        if (
            event_type == "action_selected"
            and not replay.get("selected_action")
        ):
            action_taken = RunActionResponse(
                kind=payload.get("kind"),
                arguments=payload.get("arguments", {}),
                action_id=payload.get("action_id"),
                requires_approval=payload.get("requires_approval", False),
            )

        if event_type == "approval_requested" and approval_id is None:
            approval_id = payload.get("approval_id")

        if (
            event_type == "execution_finished"
            and replay.get("latest_receipt") is None
        ):
            action_result = RunResultResponse(
                status=payload.get("status"),
                outputs=payload.get("outputs"),
                artifacts=payload.get("artifacts") or [],
                error=payload.get("error"),
            )

        if event_type in _KEY_EVENT_TYPES:
            key_events.append(
                RunKeyEventResponse(
                    type=event_type,
                    actor=event.get("actor"),
                    timestamp=event.get("timestamp"),
                    summary=event_summary(event_type, payload),
                )
            )

    memory_hits: List[RunMemoryHitResponse] = []
    if _retrieval_query_cls is not None:
        try:
            from memory_service.singleton import get_controller

            hits = get_controller().retrieve(
                _retrieval_query_cls(
                    query_text=context.goal,
                    top_k=5,
                    run_id=run_id,
                )
            )
            memory_hits = [
                RunMemoryHitResponse(
                    text=hit.text,
                    score=round(hit.score, 3),
                    memory_type=hit.memory_type,
                    stored_at=hit.stored_at,
                )
                for hit in hits
            ]
        except (_memory_backend_error, _memory_configuration_error) as exc:
            logger.warning(
                "Memory summary unavailable for run %s: %s",
                run_id,
                exc,
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
        )

    return RunSummaryResponse(
        run_id=run_id,
        goal=context.goal,
        state=str(replay.get("state") or context.state.value),
        created_at=context.created_at,
        updated_at=context.updated_at,
        plan=plan,
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
        discrepancies=_list_of_strings(replay.get("discrepancies")),
        memory_hits=memory_hits,
        key_events=key_events[-12:],
        event_count=int(replay.get("event_count") or len(events)),
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
