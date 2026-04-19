#!/usr/bin/env python3
"""Export frontend API fixtures from backend-owned response models."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.server_models import (
    AutonomySubsystemStatus,
    DatabaseSubsystemStatus,
    LLMSubsystemStatus,
    MemorySubsystemStatus,
    StorageSubsystemStatus,
    SubsystemsResponse,
)
from hca.api.models import (
    RunActionBindingResponse,
    RunApprovalDecisionResponse,
    RunApprovalGrantResponse,
    RunApprovalRequestResponse,
    RunApprovalResponse,
    RunArtifactDetailResponse,
    RunArtifactListResponse,
    RunArtifactResponse,
    RunEventListResponse,
    RunEventResponse,
    RunListResponse,
    RunSummaryResponse,
)
from hca.paths import relative_run_storage_path
from memory_service import DeleteMemoryResponse, MemoryListItem, MemoryListResponse


DEFAULT_OUTPUT = REPO_ROOT / "frontend" / "src" / "lib" / "api.fixtures.generated.json"


def _timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(
        timezone.utc
    )


def build_fixtures() -> dict[str, object]:
    approval_binding_model = RunActionBindingResponse(
        tool_name="store_note",
        target="storage/memory/operator-note.md",
        normalized_arguments={"note": "Needs approval follow-up"},
        action_class="medium",
        requires_approval=True,
        policy_snapshot={
            "requires_approval": True,
            "retention": "operator_review",
        },
        policy_fingerprint="policy-store-note",
        action_fingerprint="action-store-note",
    )
    approval_binding = approval_binding_model.model_dump(mode="json")

    pending_approval_model = RunApprovalResponse(
        approval_id="approval-1",
        status="pending",
        expired=False,
        request=RunApprovalRequestResponse(
            approval_id="approval-1",
            run_id="run-awaiting",
            action_id="action-awaiting-1",
            action_kind="store_note",
            action_class="medium",
            binding=approval_binding_model,
            reason="Write access is gated for operator review.",
            requested_at=_timestamp("2026-04-13T15:10:00Z"),
            expires_at=None,
        ),
        decision=None,
        grant=None,
        consumption=None,
        corruption_count=0,
    )
    pending_approval = pending_approval_model.model_dump(mode="json")

    subsystem_fixture = SubsystemsResponse(
        status="degraded",
        consistency_check_passed=True,
        replay_authority="local_store",
        hca_runtime_authority="python_hca_runtime",
        database=DatabaseSubsystemStatus(
            enabled=False,
            status="disabled",
            detail=(
                "Mongo-backed /api/status persistence is disabled because "
                "MONGO_URL and DB_NAME are unset. Replay-backed HCA and "
                "memory routes remain available without Mongo."
            ),
            mongo_status_mode="disabled",
            mongo_scope="status_only",
        ),
        memory=MemorySubsystemStatus(
            backend="python",
            uses_sidecar=False,
            status="healthy",
            detail="Python in-process memory controller is the active local memory authority at /tmp/hca/memory",
            memory_backend_mode="local",
            service_available=None,
            service_url=None,
        ),
        storage=StorageSubsystemStatus(
            status="writable",
            detail="HCA storage root and memory storage are writable",
            root="/tmp/hca",
            memory_dir="/tmp/hca/memory",
        ),
        llm=LLMSubsystemStatus(
            status="missing",
            detail=(
                "EMERGENT_LLM_KEY is missing; LLM-backed modules will fall back when possible"
            ),
        ),
        autonomy=AutonomySubsystemStatus(
            enabled=True,
            running=True,
            active_agents=1,
            active_runs=1,
            pending_triggers=2,
            pending_escalations=1,
            loop_running=True,
            kill_switch_active=False,
            kill_switch_reason=None,
            kill_switch_set_at=None,
            last_tick_at=_timestamp("2026-04-19T08:00:00Z"),
            last_error=None,
            last_evaluator_decision="escalate",
            dedupe_keys_tracked=4,
            recent_runs=[
                {
                    "agent_id": "agent-1",
                    "trigger_id": "trigger-1",
                    "run_id": "run-autonomy-1",
                }
            ],
            budget_ledgers=[
                {
                    "agent_id": "agent-1",
                    "launched_runs_total": 4,
                    "active_runs": 1,
                    "total_steps_observed": 6,
                    "total_retries_used": 1,
                    "last_run_started_at": _timestamp("2026-04-19T07:58:00Z"),
                    "last_run_completed_at": None,
                    "last_budget_breach_at": None,
                    "updated_at": _timestamp("2026-04-19T08:00:00Z"),
                }
            ],
            last_checkpoint={
                "agent_id": "agent-1",
                "trigger_id": "trigger-1",
                "run_id": "run-autonomy-1",
                "status": "awaiting_approval",
                "attempt": 1,
                "last_event_id": "event-1",
                "last_state": "awaiting_approval",
                "last_decision": "escalate",
                "resume_allowed": False,
                "safe_to_continue": False,
                "kill_switch_observed": False,
                "idempotency": "unknown",
                "dedupe_key": "inbox:item-1",
                "checkpointed_at": _timestamp("2026-04-19T08:00:00Z"),
                "budget_snapshot": {
                    "runs_launched": 4,
                    "parallel_runs": 1,
                    "steps_in_current_run": 2,
                    "retries_for_current_step": 1,
                },
            },
        ),
    ).model_dump(mode="json")

    run_summary_model = RunSummaryResponse(
        run_id="run-completed",
        goal="Successful retrieval",
        state="completed",
        created_at=_timestamp("2026-04-13T15:00:00Z"),
        updated_at=_timestamp("2026-04-13T15:05:00Z"),
        plan={
            "strategy": "information_retrieval_strategy",
            "action": "retrieve_memory",
            "planning_mode": "planner",
            "confidence": 0.88,
            "memory_context_used": True,
            "memory_retrieval_status": "hit",
            "memory_retrieval_error": None,
            "rationale": "Prior release context is available.",
        },
        perception={
            "intent_class": "lookup_request",
            "intent": "Find the latest release notes",
            "perception_mode": "classifier",
            "fallback_reason": None,
            "llm_attempted": True,
        },
        critique={
            "verdict": "approved",
            "alignment": 0.93,
            "feasibility": 0.86,
            "safety": 0.98,
            "confidence_delta": 0.08,
            "llm_powered": True,
            "fallback_reason": None,
            "issues": ["Response should mention the source artifact."],
            "rationale": "Retrieval is safe and well scoped.",
        },
        action_taken={
            "kind": "retrieve_memory",
            "arguments": {"scope": "release-notes"},
            "action_id": "action-1",
            "requires_approval": False,
        },
        action_result={
            "status": "success",
            "outputs": {},
            "artifacts": [],
            "error": None,
        },
        approval_id=None,
        approval=None,
        last_approval_decision=None,
        latest_receipt={"status": "success"},
        artifacts=[{"artifact_id": "artifact-1"}, {"artifact_id": "artifact-2"}],
        artifacts_count=2,
        memory_counts={"retrieved": 2},
        memory_outcomes={"retrieval": ["release-notes", "summary"]},
        active_workflow={
            "workflow_class": "RetrievalWorkflow",
            "strategy": "information_retrieval_strategy",
            "workflow_id": "wf-1",
        },
        workflow_budget={"consumed_steps": 2, "max_steps": 4},
        workflow_checkpoint={
            "current_step_id": "return_result",
            "current_step_index": 1,
        },
        workflow_step_history=[
            {
                "step_id": "fetch",
                "step_key": "fetch_memory",
                "tool_name": "memvid",
                "status": "completed",
                "action_id": "action-1",
                "touched_paths": ["storage/memory/release.json"],
            },
        ],
        workflow_artifacts=[{"artifact_id": "artifact-1"}],
        workflow_outcome={
            "terminal_event": "run_completed",
            "reason": "answer returned",
            "workflow_step_id": None,
            "next_step_id": None,
        },
        discrepancies=[],
        memory_hits=[
            {
                "text": "Release summaries should cite the most recent approved notes.",
                "score": 0.92,
                "memory_type": "procedure",
                "stored_at": _timestamp("2026-04-13T14:58:00Z"),
            },
        ],
        key_events=[
            {
                "type": "approval_requested",
                "actor": "planner",
                "timestamp": _timestamp("2026-04-13T15:02:00Z"),
                "summary": "Action needs approval",
            },
        ],
        event_count=8,
        metrics={
            "run_duration_ms": 4321,
            "tool_latency": {"count": 2, "total_ms": 310, "max_ms": 180, "last_ms": 130},
            "memory_retrieval_latency": {"count": 1, "total_ms": 80, "max_ms": 80, "last_ms": 80},
            "memory_commit_latency": {"count": 0, "total_ms": 0, "max_ms": 0, "last_ms": None},
        },
    )
    run_summary = run_summary_model.model_dump(mode="json")

    awaiting_summary_model = RunSummaryResponse(
        run_id="run-awaiting",
        goal="Needs approval follow-up",
        state="awaiting_approval",
        created_at=_timestamp("2026-04-13T15:09:00Z"),
        updated_at=_timestamp("2026-04-13T15:10:00Z"),
        plan={
            "strategy": "artifact_authoring_strategy",
            "action": "store_note",
            "planning_mode": "rule_based_fallback",
            "confidence": 0.55,
            "memory_context_used": False,
            "memory_retrieval_status": None,
            "memory_retrieval_error": None,
            "rationale": "The requested note should be stored after operator approval.",
        },
        perception={
            "intent_class": "store_note",
            "intent": "store",
            "perception_mode": "rule_based_fallback",
            "fallback_reason": None,
            "llm_attempted": True,
        },
        critique={
            "verdict": "revise",
            "alignment": 0.7,
            "feasibility": 0.8,
            "safety": 0.9,
            "confidence_delta": -0.05,
            "llm_powered": False,
            "fallback_reason": None,
            "issues": ["Approval required before writing the note."],
            "rationale": "Write access is gated for operator review.",
        },
        action_taken={
            "kind": "store_note",
            "arguments": {"note": "Needs approval follow-up"},
            "action_id": "action-awaiting-1",
            "requires_approval": True,
        },
        action_result={
            "status": None,
            "outputs": None,
            "artifacts": [],
            "error": None,
        },
        approval_id="approval-1",
        approval=pending_approval_model,
        last_approval_decision=None,
        latest_receipt=None,
        artifacts=[],
        artifacts_count=0,
        memory_counts={"episodic": 0},
        memory_outcomes={"episodic_memory_writes": 0},
        active_workflow=None,
        workflow_budget=None,
        workflow_checkpoint=None,
        workflow_step_history=[],
        workflow_artifacts=[],
        workflow_outcome={
            "terminal_event": None,
            "reason": None,
            "workflow_step_id": None,
            "next_step_id": None,
        },
        discrepancies=[],
        memory_hits=[],
        key_events=[
            {
                "type": "approval_requested",
                "actor": "runtime",
                "timestamp": _timestamp("2026-04-13T15:10:00Z"),
                "summary": "Approval requested (id=approval-1)",
            },
        ],
        event_count=6,
        metrics={
            "run_duration_ms": 1600,
            "tool_latency": {"count": 0, "total_ms": 0, "max_ms": 0, "last_ms": None},
            "memory_retrieval_latency": {"count": 0, "total_ms": 0, "max_ms": 0, "last_ms": None},
            "memory_commit_latency": {"count": 0, "total_ms": 0, "max_ms": 0, "last_ms": None},
        },
    )
    awaiting_summary = awaiting_summary_model.model_dump(mode="json")

    approved_summary = RunSummaryResponse(
        **{
            **awaiting_summary,
            "state": "completed",
            "updated_at": "2026-04-13T15:12:00Z",
            "approval": RunApprovalResponse(
                approval_id="approval-1",
                status="granted",
                expired=False,
                request=RunApprovalRequestResponse(
                    approval_id="approval-1",
                    run_id="run-awaiting",
                    action_id="action-awaiting-1",
                    action_kind="store_note",
                    action_class="medium",
                    binding=approval_binding_model,
                    reason="Write access is gated for operator review.",
                    requested_at=_timestamp("2026-04-13T15:10:00Z"),
                    expires_at=None,
                ),
                decision=RunApprovalDecisionResponse(
                    approval_id="approval-1",
                    decision="granted",
                    actor="user",
                    reason="Approved by operator",
                    binding=approval_binding_model,
                    decided_at=_timestamp("2026-04-13T15:11:00Z"),
                    expires_at=None,
                ),
                grant=RunApprovalGrantResponse(
                    approval_id="approval-1",
                    token="eval-token",
                    actor="user",
                    binding=approval_binding_model,
                    granted_at=_timestamp("2026-04-13T15:11:30Z"),
                    expires_at=None,
                ),
                consumption=None,
                corruption_count=0,
            ).model_dump(mode="json"),
            "last_approval_decision": "granted",
            "action_result": {
                "status": "success",
                "outputs": {
                    "note_path": str(
                        relative_run_storage_path(
                            "run-awaiting",
                            "artifacts",
                            "note.txt",
                        )
                    )
                },
                "artifacts": [],
                "error": None,
            },
            "latest_receipt": {"status": "success"},
            "artifacts": [{"artifact_id": "artifact-awaiting-1"}],
            "artifacts_count": 1,
            "event_count": 9,
            "workflow_outcome": {
                "terminal_event": "run_completed",
                "reason": "note stored",
                "workflow_step_id": None,
                "next_step_id": None,
            },
        }
    ).model_dump(mode="json")

    run_events = RunEventListResponse(
        run_id="run-completed",
        total=3,
        records=[
            RunEventResponse(
                event_id="event-1",
                run_id="run-completed",
                event_type="approval_requested",
                actor="planner",
                timestamp=_timestamp("2026-04-13T15:02:00Z"),
                summary="Action needs approval",
                payload={"approval_id": "approval-1", "reason": "write access"},
                prior_state="running",
                next_state="awaiting_approval",
                is_key_event=True,
            ),
            RunEventResponse(
                event_id="event-2",
                run_id="run-completed",
                event_type="workflow_selected",
                actor="planner",
                timestamp=_timestamp("2026-04-13T15:01:00Z"),
                summary="Workflow selected",
                payload={"workflow_class": "RetrievalWorkflow"},
                prior_state="running",
                next_state="running",
                is_key_event=False,
            ),
            RunEventResponse(
                event_id="event-3",
                run_id="run-completed",
                event_type="run_completed",
                actor="runtime",
                timestamp=_timestamp("2026-04-13T15:05:00Z"),
                summary="Run completed",
                payload={"status": "success"},
                prior_state="running",
                next_state="completed",
                is_key_event=True,
            ),
        ],
    ).model_dump(mode="json")

    artifact_records = [
        RunArtifactResponse(
            artifact_id="artifact-1",
            run_id="run-completed",
            action_id="action-1",
            kind="summary",
            path="artifacts/release-summary.md",
            source_action_ids=["action-1"],
            file_paths=["artifacts/release-summary.md"],
            hashes={"sha256": "abc"},
            workflow_id="wf-1",
            approval_id=None,
            metadata={"format": "markdown"},
            created_at=_timestamp("2026-04-13T15:05:00Z"),
            content_available=True,
        ),
        RunArtifactResponse(
            artifact_id="artifact-2",
            run_id="run-completed",
            action_id="action-2",
            kind="trace",
            path="artifacts/retrieval-trace.json",
            source_action_ids=["action-2"],
            file_paths=["artifacts/retrieval-trace.json"],
            hashes={"sha256": "def"},
            workflow_id="wf-1",
            approval_id=None,
            metadata={"format": "json"},
            created_at=_timestamp("2026-04-13T15:04:00Z"),
            content_available=True,
        ),
    ]
    artifact_list = RunArtifactListResponse(
        run_id="run-completed",
        total=2,
        records=artifact_records,
    ).model_dump(mode="json")

    artifact_detail = RunArtifactDetailResponse(
        **artifact_records[0].model_dump(mode="json"),
        content="# Release Summary\n\n- Item one",
        size_bytes=128,
        truncated=False,
    ).model_dump(mode="json")

    trace_artifact_detail = RunArtifactDetailResponse(
        **artifact_records[1].model_dump(mode="json"),
        content='{"status":"ok"}',
        size_bytes=64,
        truncated=False,
    ).model_dump(mode="json")

    memory_list = MemoryListResponse(
        total=2,
        records=[
            MemoryListItem(
                memory_id="memory-1",
                memory_type="procedure",
                run_id="run-1",
                stored_at=_timestamp("2026-04-13T14:00:00Z"),
                text="Release summaries should always mention the approval state and the artifact path.",
            ),
            MemoryListItem(
                memory_id="memory-2",
                memory_type="preference",
                run_id="run-2",
                stored_at=_timestamp("2026-04-13T14:05:00Z"),
                text="Database credentials rotate every 30 days and need a reminder record.",
            ),
        ],
    ).model_dump(mode="json")

    delete_memory = DeleteMemoryResponse(
        deleted=True,
        memory_id="memory-1",
    ).model_dump(mode="json")

    return {
        "APPROVAL_BINDING_FIXTURE": approval_binding,
        "PENDING_APPROVAL_FIXTURE": pending_approval,
        "SUBSYSTEMS_FIXTURE": subsystem_fixture,
        "RUN_SUMMARY_FIXTURE": run_summary,
        "RUN_AWAITING_SUMMARY_FIXTURE": awaiting_summary,
        "RUN_APPROVED_SUMMARY_FIXTURE": approved_summary,
        "RUN_LIST_FIXTURE": RunListResponse(
            records=[awaiting_summary_model, run_summary_model],
            total=2,
        ).model_dump(mode="json"),
        "RUN_EVENTS_FIXTURE": run_events,
        "RUN_ARTIFACTS_FIXTURE": artifact_list,
        "RUN_ARTIFACT_DETAIL_FIXTURE": artifact_detail,
        "RUN_TRACE_ARTIFACT_DETAIL_FIXTURE": trace_artifact_detail,
        "MEMORY_LIST_FIXTURE": memory_list,
        "DELETE_MEMORY_FIXTURE": delete_memory,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    fixtures = build_fixtures()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(fixtures, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())