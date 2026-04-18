"""Runtime orchestrator for the hybrid cognitive agent."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from functools import lru_cache
from time import perf_counter
from typing import Any, Dict, Optional

from hca.common.enums import (
    ActionClass,
    ControlSignal,
    EventType,
    MemoryType,
    ReceiptStatus,
    RuntimeState,
    WorkflowStepStatus,
)
from hca.common.time import utc_now
from hca.common.types import (
    ActionCandidate,
    ArtifactSummary,
    ApprovalConsumption,
    ApprovalGrant,
    MetaAssessment,
    ApprovalRequest,
    MemoryRecord,
    MutationResult,
    RunContext,
    WorkflowBudget,
    WorkflowCheckpoint,
    WorkflowPlan,
    WorkflowStep,
    WorkflowStepRecord,
)
from hca.executor.approvals import validate_resume_approval
from hca.executor.executor import Executor
from hca.executor.tool_registry import (
    ToolValidationError,
    build_action_candidate,
    canonicalize_action_candidate,
)
from hca.memory.episodic_store import EpisodicStore
from hca.meta.monitor import assess
from hca.meta.self_model import capability_summary
from hca.modules import Planner, Critic, TextPerception, ToolReasoner
from hca.modules.workflow_chains import resolve_step_arguments
from hca.paths import ensure_repo_root_on_sys_path
from hca.prediction.action_scoring import score_actions, score_workflow_plans
from hca.runtime.snapshots import build_runtime_snapshot
from hca.runtime.state_machine import assert_transition
from hca.storage import (
    append_consumption as append_approval_consumption,
    append_grant as append_approval_grant,
    append_denial as append_approval_denial,
    append_event,
    append_request as append_approval_request,
    append_snapshot,
    load_run,
    run_operation_lock,
    save_run,
)
from hca.workspace.broadcast import broadcast
from hca.workspace.recurrence import run_recurrence
from hca.workspace.workspace import Workspace


@lru_cache(maxsize=1)
def _load_memory_service_bindings():
    ensure_repo_root_on_sys_path()
    try:
        from memory_service import CandidateMemory as candidate_memory_cls
        from memory_service import Provenance as provenance_cls
        from memory_service.singleton import get_controller
    except ImportError:
        return None, None, None

    return get_controller, candidate_memory_cls, provenance_cls


class Runtime:
    def __init__(
        self, workspace_capacity: int = 7, replan_budget: int = 3
    ) -> None:
        self.workspace_capacity = workspace_capacity
        self.replan_budget = replan_budget
        self._remaining_replan = replan_budget
        self.executor = Executor()
        self.modules: list[Any] = [
            Planner(),
            Critic(),
            TextPerception(),
            ToolReasoner(),
        ]
        self._current_state: RuntimeState = RuntimeState.created
        self._execution_failure_count = 0

    def _persist_context(self, context: RunContext) -> None:
        context.updated_at = utc_now()
        save_run(context)

    def _set_pending_approval(
        self,
        context: RunContext,
        approval_id: Optional[str],
    ) -> None:
        if context.pending_approval_id == approval_id:
            return
        context.pending_approval_id = approval_id
        self._persist_context(context)

    def _load_authoritative_pending_approval(
        self,
        run_id: str,
        approval_id: str,
        *,
        allowed_statuses: tuple[str, ...] = ("pending",),
    ) -> tuple[RunContext, Dict[str, Any], Optional[Dict[str, Any]]]:
        context = load_run(run_id)
        if not context:
            raise ValueError(f"Run {run_id} not found")

        from hca.runtime.replay import reconstruct_state

        replayed = reconstruct_state(run_id)
        approval = replayed.get("approval")
        if not isinstance(approval, dict):
            approval = None

        replay_state = str(replayed.get("state") or context.state.value)
        pending_from_storage = (
            approval is not None
            and approval.get("status") in allowed_statuses
        )
        if replay_state != RuntimeState.awaiting_approval.value and not (
            context.state == RuntimeState.awaiting_approval
            and pending_from_storage
        ):
            if approval is not None and approval.get("status") is not None:
                status = str(approval["status"]).replace("_", " ")
                raise ValueError(f"approval is {status}")
            raise ValueError("run is not awaiting approval")

        authoritative_pending_id = None
        if approval is not None and approval.get("status") in allowed_statuses:
            candidate_id = approval.get("approval_id")
            if isinstance(candidate_id, str):
                authoritative_pending_id = candidate_id
        if authoritative_pending_id is None:
            candidate_id = replayed.get("pending_approval_id")
            if isinstance(candidate_id, str):
                authoritative_pending_id = candidate_id

        if authoritative_pending_id is None:
            raise ValueError("run has no pending approval")
        if authoritative_pending_id != approval_id:
            raise ValueError("approval id does not match pending approval")
        if (
            approval is not None
            and approval.get("status") not in allowed_statuses
        ):
            status = str(approval["status"]).replace("_", " ")
            raise ValueError(f"approval is {status}")

        needs_persist = False
        if context.state != RuntimeState.awaiting_approval:
            context.state = RuntimeState.awaiting_approval
            needs_persist = True
        if context.pending_approval_id != approval_id:
            context.pending_approval_id = approval_id
            needs_persist = True
        if needs_persist:
            self._persist_context(context)

        self._current_state = context.state
        return context, replayed, approval

    def _set_state(
        self,
        context: RunContext,
        target: RuntimeState,
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Enforce transition, persist it, and log the state change."""
        current = context.state
        if (
            current == RuntimeState.created
            and self._current_state != RuntimeState.created
        ):
            current = self._current_state
            context.state = current
        self._current_state = current
        assert_transition(current, target)
        context.state = target
        self._current_state = target
        self._persist_context(context)
        append_event(
            context,
            EventType.state_transition,
            "runtime",
            payload or {"to": target.value},
            prior_state=current,
            next_state=target,
        )

    def _write_snapshot(
        self,
        context: RunContext,
        workspace: Any,
        selected_action: Optional[ActionCandidate] = None,
        latest_receipt_id: Optional[str] = None,
        promotion_candidates: Optional[list[dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        snapshot = build_runtime_snapshot(
            run_id=context.run_id,
            state=context.state,
            workspace_or_items=workspace,
            selected_action=selected_action,
            pending_approval_id=context.pending_approval_id,
            latest_receipt_id=latest_receipt_id,
            promotion_candidates=promotion_candidates,
            active_workflow=context.active_workflow,
            workflow_budget=context.workflow_budget,
            workflow_checkpoint=context.workflow_checkpoint,
            workflow_step_history=context.workflow_step_history,
            workflow_artifacts=context.workflow_artifacts,
        )
        append_snapshot(context.run_id, snapshot)
        append_event(
            context,
            EventType.snapshot_written,
            "runtime",
            {
                "state": snapshot["state"],
                "pending_approval_id": snapshot.get("pending_approval_id"),
            },
        )
        return snapshot

    @staticmethod
    def _workflow_step_index(
        workflow: WorkflowPlan,
        step_id: str,
    ) -> int:
        for index, step in enumerate(workflow.steps):
            if step.step_id == step_id:
                return index
        raise ValueError(f"Workflow step not found: {step_id}")

    def _select_action(
        self,
        context: RunContext,
        candidate: ActionCandidate,
    ) -> None:
        append_event(
            context,
            EventType.action_selected,
            "runtime",
            candidate.model_dump(mode="json"),
        )

    def _candidate_for_workflow_step(
        self,
        context: RunContext,
        workflow: WorkflowPlan,
        step: WorkflowStep,
        *,
        provenance: Optional[list[str]] = None,
        step_history: Optional[list[WorkflowStepRecord]] = None,
    ) -> ActionCandidate:
        arguments = resolve_step_arguments(
            workflow,
            step,
            step_history=(
                context.workflow_step_history
                if step_history is None
                else step_history
            ),
        )
        return build_action_candidate(
            step.tool_name,
            arguments,
            provenance=provenance
            or [
                f"workflow:{workflow.workflow_id}",
                step.step_key or step.step_id,
            ],
            workflow_id=workflow.workflow_id,
            workflow_step_id=step.step_id,
        )

    def _activate_workflow(
        self,
        context: RunContext,
        workflow: WorkflowPlan,
        *,
        score: Optional[Dict[str, float]] = None,
    ) -> None:
        context.active_workflow = workflow
        configured_max_steps = (
            workflow.max_steps
            if workflow.max_steps > 0
            else len(workflow.steps)
        )
        budget = WorkflowBudget(
            max_steps=max(1, configured_max_steps),
            consumed_steps=0,
        )
        context.workflow_budget = budget
        context.workflow_checkpoint = WorkflowCheckpoint(
            workflow_id=workflow.workflow_id,
            current_step_index=0,
            current_step_id=(
                workflow.steps[0].step_id if workflow.steps else None
            ),
        )
        context.workflow_step_history = []
        context.workflow_artifacts = []
        self._persist_context(context)
        append_event(
            context,
            EventType.workflow_selected,
            "runtime",
            {
                "workflow_id": workflow.workflow_id,
                "workflow_class": workflow.workflow_class.value,
                "strategy": workflow.strategy,
                "step_count": len(workflow.steps),
                "max_steps": budget.max_steps,
                "score": score,
            },
        )

    def _request_approval(
        self,
        context: RunContext,
        candidate: ActionCandidate,
        *,
        workspace: Optional[Workspace] = None,
    ) -> str:
        approval_id = str(uuid.uuid4())
        request = ApprovalRequest(
            approval_id=approval_id,
            run_id=context.run_id,
            action_id=candidate.action_id,
            action_kind=candidate.kind,
            action_class=candidate.action_class or ActionClass.medium,
            binding=candidate.binding,
            reason="Action requires approval",
            expires_at=utc_now() + timedelta(minutes=15),
        )
        append_approval_request(context.run_id, request)
        self._set_pending_approval(context, approval_id)
        append_event(
            context,
            EventType.approval_requested,
            "runtime",
            {
                "approval_id": approval_id,
                "action_id": candidate.action_id,
                "action_kind": candidate.kind,
                "workflow_id": candidate.workflow_id,
                "workflow_step_id": candidate.workflow_step_id,
                "action_fingerprint": (
                    candidate.binding.action_fingerprint
                    if candidate.binding is not None
                    else None
                ),
                "policy_fingerprint": (
                    candidate.binding.policy_fingerprint
                    if candidate.binding is not None
                    else None
                ),
                "expires_at": (
                    request.expires_at.isoformat()
                    if request.expires_at
                    else None
                ),
            },
        )
        self._set_state(context, RuntimeState.awaiting_approval)
        self._write_snapshot(
            context,
            workspace or [],
            selected_action=candidate,
        )
        return context.run_id

    @staticmethod
    def _require_matching_pending_approval(
        context: RunContext,
        approval_id: str,
    ) -> None:
        if context.pending_approval_id is None:
            raise ValueError("run has no pending approval")
        if context.pending_approval_id != approval_id:
            raise ValueError("approval id does not match pending approval")

    def _record_workflow_step(
        self,
        context: RunContext,
        candidate: ActionCandidate,
        receipt_payload: Dict[str, Any],
    ) -> Optional[WorkflowStepRecord]:
        workflow = context.active_workflow
        step_id = candidate.workflow_step_id
        if workflow is None or candidate.workflow_id != workflow.workflow_id:
            return None
        if step_id is None:
            return None

        step = next(
            (
                current
                for current in workflow.steps
                if current.step_id == step_id
            ),
            None,
        )
        if step is None:
            return None

        status = (
            WorkflowStepStatus.completed
            if receipt_payload.get("status") == ReceiptStatus.success.value
            else WorkflowStepStatus.failed
        )
        artifact_summaries = [
            ArtifactSummary.model_validate(summary)
            for summary in receipt_payload.get("artifact_summaries") or []
        ]
        mutation_payload = receipt_payload.get("mutation_result")
        record = WorkflowStepRecord(
            step_id=step.step_id,
            step_key=step.step_key,
            tool_name=step.tool_name,
            status=status,
            action_id=candidate.action_id,
            receipt_id=receipt_payload.get("receipt_id"),
            approval_id=receipt_payload.get("approval_id"),
            outputs=receipt_payload.get("outputs"),
            touched_paths=receipt_payload.get("touched_paths") or [],
            artifacts=receipt_payload.get("artifacts") or [],
            artifact_summaries=artifact_summaries,
            mutation_result=(
                None
                if mutation_payload is None
                else MutationResult.model_validate(mutation_payload)
            ),
        )

        context.workflow_step_history.append(record)
        if artifact_summaries:
            seen_paths = {
                artifact.path for artifact in context.workflow_artifacts
            }
            for artifact in artifact_summaries:
                if artifact.path not in seen_paths:
                    context.workflow_artifacts.append(artifact)
                    seen_paths.add(artifact.path)

        if context.workflow_budget is not None:
            context.workflow_budget.consumed_steps += 1

        if context.workflow_checkpoint is not None:
            step_index = self._workflow_step_index(workflow, step.step_id)
            context.workflow_checkpoint.latest_receipt_id = (
                receipt_payload.get("receipt_id")
            )
            context.workflow_checkpoint.latest_artifact_paths = list(
                dict.fromkeys(
                    context.workflow_checkpoint.latest_artifact_paths
                    + (receipt_payload.get("artifacts") or [])
                )
            )
            if status == WorkflowStepStatus.completed:
                context.workflow_checkpoint.completed_step_ids = list(
                    dict.fromkeys(
                        context.workflow_checkpoint.completed_step_ids
                        + [step.step_id]
                    )
                )
                next_index = step_index + 1
            else:
                next_index = step_index
            context.workflow_checkpoint.current_step_index = next_index
            context.workflow_checkpoint.current_step_id = (
                workflow.steps[next_index].step_id
                if next_index < len(workflow.steps)
                else None
            )

        self._persist_context(context)
        append_event(
            context,
            EventType.workflow_step_finished,
            "runtime",
            {
                "workflow_id": workflow.workflow_id,
                "workflow_step_id": step.step_id,
                "step_key": step.step_key,
                "tool_name": step.tool_name,
                "status": status.value,
                "receipt_id": receipt_payload.get("receipt_id"),
                "approval_id": receipt_payload.get("approval_id"),
                "artifacts": receipt_payload.get("artifacts") or [],
                "touched_paths": receipt_payload.get("touched_paths") or [],
            },
        )
        return record

    def _continue_workflow(
        self,
        context: RunContext,
        candidate: ActionCandidate,
        receipt_payload: Dict[str, Any],
        *,
        workspace: Optional[Workspace] = None,
    ) -> str:
        workflow = context.active_workflow
        if workflow is None or candidate.workflow_id != workflow.workflow_id:
            raise ValueError(
                "workflow continuation requires an active workflow"
            )

        self._record_workflow_step(context, candidate, receipt_payload)

        if receipt_payload.get("status") != ReceiptStatus.success.value:
            self._execution_failure_count += 1
            append_event(
                context,
                EventType.workflow_terminated,
                "runtime",
                {
                    "workflow_id": workflow.workflow_id,
                    "reason": "step_failed",
                    "workflow_step_id": candidate.workflow_step_id,
                    "receipt_id": receipt_payload.get("receipt_id"),
                },
            )
            return self._fail_run(
                context,
                "workflow_step_failed",
                details={
                    "workflow_id": workflow.workflow_id,
                    "workflow_step_id": candidate.workflow_step_id,
                    "failure_count": self._execution_failure_count,
                    "status": receipt_payload.get("status"),
                },
                workspace=workspace,
                selected_action=candidate,
                latest_receipt_id=receipt_payload.get("receipt_id"),
            )

        checkpoint = context.workflow_checkpoint
        next_index = (
            checkpoint.current_step_index
            if checkpoint is not None
            else len(workflow.steps)
        )
        if next_index >= len(workflow.steps):
            self._set_state(context, RuntimeState.reporting)
            append_event(
                context,
                EventType.report_emitted,
                "runtime",
                {
                    "action_id": candidate.action_id,
                    "status": receipt_payload.get("status"),
                    "failure_count": self._execution_failure_count,
                    "workflow_id": workflow.workflow_id,
                },
            )
            append_event(
                context,
                EventType.workflow_terminated,
                "runtime",
                {
                    "workflow_id": workflow.workflow_id,
                    "reason": "completed",
                    "receipt_id": receipt_payload.get("receipt_id"),
                },
            )
            self._set_state(context, RuntimeState.completed)
            append_event(
                context,
                EventType.run_completed,
                "runtime",
                {
                    "receipt_id": receipt_payload.get("receipt_id"),
                    "workflow_id": workflow.workflow_id,
                },
            )
            self._write_snapshot(
                context,
                workspace or [],
                selected_action=candidate,
                latest_receipt_id=receipt_payload.get("receipt_id"),
            )
            return context.run_id

        next_step = workflow.steps[next_index]
        if (
            context.workflow_budget is not None
            and context.workflow_budget.remaining_steps <= 0
        ):
            append_event(
                context,
                EventType.workflow_budget_exhausted,
                "runtime",
                {
                    "workflow_id": workflow.workflow_id,
                    "max_steps": context.workflow_budget.max_steps,
                    "consumed_steps": context.workflow_budget.consumed_steps,
                    "next_step_id": next_step.step_id,
                },
            )
            append_event(
                context,
                EventType.workflow_terminated,
                "runtime",
                {
                    "workflow_id": workflow.workflow_id,
                    "reason": "budget_exhausted",
                    "consumed_steps": (
                        context.workflow_budget.consumed_steps
                        if context.workflow_budget is not None
                        else None
                    ),
                    "next_step_id": next_step.step_id,
                },
            )
            return self._fail_run(
                context,
                "workflow_budget_exhausted",
                details={"workflow_id": workflow.workflow_id},
                workspace=workspace,
                selected_action=candidate,
                latest_receipt_id=receipt_payload.get("receipt_id"),
            )

        try:
            next_candidate = self._candidate_for_workflow_step(
                context,
                workflow,
                next_step,
                provenance=candidate.provenance,
            )
        except (KeyError, ToolValidationError, ValueError) as exc:
            append_event(
                context,
                EventType.workflow_terminated,
                "runtime",
                {
                    "workflow_id": workflow.workflow_id,
                    "reason": "next_step_unbuildable",
                    "workflow_step_id": next_step.step_id,
                    "error": str(exc),
                },
            )
            return self._fail_run(
                context,
                "workflow_next_step_unbuildable",
                details={
                    "workflow_id": workflow.workflow_id,
                    "workflow_step_id": next_step.step_id,
                },
                workspace=workspace,
                selected_action=candidate,
                latest_receipt_id=receipt_payload.get("receipt_id"),
            )
        self._select_action(context, next_candidate)
        if next_candidate.requires_approval:
            return self._request_approval(
                context,
                next_candidate,
                workspace=workspace,
            )
        return self._execute_and_complete(
            context,
            next_candidate,
            approved=False,
            workspace=workspace,
        )

    def _record_execution_memory(
        self,
        context: RunContext,
        candidate: ActionCandidate,
        receipt_payload: Dict[str, Any],
    ) -> None:
        import json as _json
        record = MemoryRecord(
            memory_type=MemoryType.episodic,
            run_id=context.run_id,
            subject=candidate.kind,
            content={
                "action_id": candidate.action_id,
                "action_kind": candidate.kind,
                "arguments": candidate.arguments,
                "binding": (
                    candidate.binding.model_dump(mode="json")
                    if candidate.binding is not None
                    else None
                ),
                "status": receipt_payload.get("status"),
                "artifacts": receipt_payload.get("artifacts") or [],
            },
            source_run=context.run_id,
            provenance=[candidate.action_id],
            confidence=(
                1.0
                if receipt_payload.get("status") == ReceiptStatus.success.value
                else 0.5
            ),
        )
        memory_event_context = {
            "run_id": context.run_id,
            "action_id": candidate.action_id,
            "action_kind": candidate.kind,
            "subject": record.subject,
            "workflow_id": candidate.workflow_id,
            "workflow_step_id": candidate.workflow_step_id,
            "receipt_status": receipt_payload.get("status"),
            "finalization_context": (
                "workflow_step"
                if candidate.workflow_id is not None
                else "single_action"
            ),
        }
        episodic_started_at = perf_counter()
        try:
            EpisodicStore(context.run_id).append(record)
        except Exception as exc:
            episodic_latency_ms = round(
                (perf_counter() - episodic_started_at) * 1000.0,
                3,
            )
            append_event(
                context,
                EventType.report_emitted,
                "runtime",
                {
                    "reason_code": "episodic_memory_write_failed",
                    "action_id": candidate.action_id,
                    "latency_ms": episodic_latency_ms,
                    "error_type": exc.__class__.__name__,
                    "error": str(exc),
                },
            )
            raise

        episodic_latency_ms = round(
            (perf_counter() - episodic_started_at) * 1000.0,
            3,
        )

        episodic_payload = {
            **memory_event_context,
            "record_id": record.record_id,
            "sink": "episodic_store",
            "status": "written",
            "failure_class": None,
            "memory_type": MemoryType.episodic.value,
            "latency_ms": episodic_latency_ms,
        }
        append_event(
            context,
            EventType.episodic_memory_written,
            "runtime",
            episodic_payload,
        )

        # Also ingest into the authoritative memory service (contract boundary)
        (
            get_mem_controller,
            candidate_memory_cls,
            provenance_cls,
        ) = _load_memory_service_bindings()
        if (
            get_mem_controller is not None
            and candidate_memory_cls is not None
            and provenance_cls is not None
        ):
            external_started_at = perf_counter()
            try:
                raw_text = (
                    f"{candidate.kind}: "
                    + _json.dumps(candidate.arguments, default=str)[:200]
                    + f" → {receipt_payload.get('status', 'unknown')}"
                )
                memory_id = get_mem_controller().ingest(
                    candidate_memory_cls(
                        raw_text=raw_text,
                        memory_type="episode",
                        run_id=context.run_id,
                        confidence=record.confidence,
                        salience=0.6,
                        source=provenance_cls(
                            source_type="system",
                            trust_weight=0.9,
                        ),
                        metadata={
                            "action_id": candidate.action_id,
                            "action_fingerprint": (
                                candidate.binding.action_fingerprint
                                if candidate.binding is not None
                                else None
                            ),
                        },
                    )
                )
                external_latency_ms = round(
                    (perf_counter() - external_started_at) * 1000.0,
                    3,
                )
                append_event(
                    context,
                    EventType.external_memory_written,
                    "runtime",
                    {
                        **memory_event_context,
                        "sink": "external_memory",
                        "status": "written",
                        "memory_id": memory_id,
                        "failure_class": None,
                        "latency_ms": external_latency_ms,
                    },
                )
            except Exception as exc:
                external_latency_ms = round(
                    (perf_counter() - external_started_at) * 1000.0,
                    3,
                )
                append_event(
                    context,
                    EventType.external_memory_write_failed,
                    "runtime",
                    {
                        **memory_event_context,
                        "sink": "external_memory",
                        "status": "failed",
                        "failure_class": exc.__class__.__name__,
                        "error_type": exc.__class__.__name__,
                        "error": str(exc),
                        "latency_ms": external_latency_ms,
                    },
                )

        append_event(
            context,
            EventType.memory_written,
            "runtime",
            episodic_payload,
        )

    def _fail_run(
        self,
        context: RunContext,
        reason: str,
        *,
        details: Optional[Dict[str, Any]] = None,
        workspace: Optional[Workspace] = None,
        selected_action: Optional[ActionCandidate] = None,
        latest_receipt_id: Optional[str] = None,
    ) -> str:
        state_payload = {"reason": reason, **(details or {})}
        terminal_payload = {
            "terminal_state": RuntimeState.failed.value,
            **state_payload,
        }
        if selected_action is not None:
            terminal_payload.setdefault("action_id", selected_action.action_id)
            terminal_payload.setdefault("action_kind", selected_action.kind)
        if latest_receipt_id is not None:
            terminal_payload["receipt_id"] = latest_receipt_id

        append_event(
            context,
            EventType.report_emitted,
            "runtime",
            terminal_payload,
        )
        self._set_state(context, RuntimeState.failed, state_payload)
        append_event(
            context,
            EventType.run_failed,
            "runtime",
            terminal_payload,
        )
        self._write_snapshot(
            context,
            workspace or [],
            selected_action=selected_action,
            latest_receipt_id=latest_receipt_id,
        )
        return context.run_id

    def _record_unhandled_failure(
        self,
        context: RunContext,
        exc: Exception,
    ) -> None:
        if context.state in {
            RuntimeState.completed,
            RuntimeState.failed,
            RuntimeState.halted,
        }:
            return
        self._execution_failure_count += 1
        self._fail_run(
            context,
            "unhandled_runtime_exception",
            details={
                "failure_count": self._execution_failure_count,
                "error_type": exc.__class__.__name__,
                "error": str(exc),
            },
        )

    def _halt_run(self, context: RunContext, reason: str) -> str:
        append_event(
            context,
            EventType.report_emitted,
            "runtime",
            {"terminal_state": RuntimeState.halted.value, "reason": reason},
        )
        self._set_state(context, RuntimeState.halted, {"reason": reason})
        self._write_snapshot(context, [], None)
        return context.run_id

    def _handle_control_signal(
        self,
        context: RunContext,
        assessment: MetaAssessment,
    ) -> str | None:
        signal = assessment.recommended_transition
        if signal == ControlSignal.halt:
            return self._halt_run(
                context, assessment.explanation or "halted"
            )
        if signal == ControlSignal.replan:
            if self._remaining_replan > 0:
                self._remaining_replan -= 1
                self._set_state(
                    context,
                    RuntimeState.proposing,
                    {
                        "reason": "replan_signal",
                        "remaining_replan": self._remaining_replan,
                    },
                )
                return self._step_from_proposing(
                    context,
                    Workspace(capacity=self.workspace_capacity),
                )
            append_event(
                context,
                EventType.report_emitted,
                "runtime",
                {"reason_code": "failure_loop", "remaining_replan": 0},
            )
            return None
        if signal == ControlSignal.retrieve_more:
            append_event(
                context,
                EventType.report_emitted,
                "runtime",
                {
                    "reason_code": "retrieve_more",
                    "action": "fallback_replan",
                },
            )
            if self._remaining_replan > 0:
                self._remaining_replan -= 1
                self._set_state(
                    context,
                    RuntimeState.proposing,
                    {
                        "reason": "retrieve_more_signal",
                        "remaining_replan": self._remaining_replan,
                    },
                )
                return self._step_from_proposing(
                    context,
                    Workspace(capacity=self.workspace_capacity),
                )
            return None
        if signal == ControlSignal.ask_user:
            append_event(
                context,
                EventType.report_emitted,
                "runtime",
                {
                    "reason_code": "ask_user",
                    "message": assessment.explanation,
                },
            )
            self._set_state(
                context,
                RuntimeState.awaiting_approval,
                {"reason": assessment.explanation},
            )
            self._write_snapshot(context, [], None)
            return context.run_id
        return None

    def create_run(self, goal: str, user_id: str | None = None) -> RunContext:
        context = RunContext(goal=goal, user_id=user_id)
        context.active_environment = "default"
        context.state = RuntimeState.created
        self._persist_context(context)
        append_event(
            context,
            EventType.run_created,
            "runtime",
            {"goal": goal},
        )
        return context

    def create_autonomous_run(
        self,
        goal: str,
        *,
        user_id: str | None = None,
        autonomy_agent_id: str,
        autonomy_trigger_id: str,
        autonomy_mode: str,
    ) -> RunContext:
        """Create a run carrying autonomy metadata.

        This wrapper exists solely so the autonomy supervisor can launch runs
        through the ordinary runtime path. No autonomy-specific branching is
        introduced inside core execution logic.
        """
        context = RunContext(goal=goal, user_id=user_id)
        context.active_environment = "default"
        context.state = RuntimeState.created
        context.autonomy_agent_id = autonomy_agent_id
        context.autonomy_trigger_id = autonomy_trigger_id
        context.autonomy_mode = autonomy_mode
        self._persist_context(context)
        append_event(
            context,
            EventType.run_created,
            "runtime",
            {
                "goal": goal,
                "autonomy_agent_id": autonomy_agent_id,
                "autonomy_trigger_id": autonomy_trigger_id,
                "autonomy_mode": autonomy_mode,
            },
        )
        return context

    def run(self, goal: str, user_id: str | None = None) -> str:
        context = self.create_run(goal, user_id)
        self._current_state = RuntimeState.created
        self._remaining_replan = self.replan_budget
        self._execution_failure_count = 0
        try:
            return self._step(context)
        except Exception as exc:
            self._record_unhandled_failure(context, exc)
            raise

    def grant_approval(
        self,
        run_id: str,
        approval_id: str,
        token: str,
        *,
        actor: str = "user",
        expires_at: Optional[datetime] = None,
    ) -> str:
        with run_operation_lock(run_id):
            self._load_authoritative_pending_approval(run_id, approval_id)
            append_approval_grant(
                run_id,
                ApprovalGrant(
                    approval_id=approval_id,
                    token=token,
                    actor=actor,
                    expires_at=expires_at,
                ),
            )
            return self.resume(run_id, approval_id, token)

    def deny_approval(
        self, run_id: str, approval_id: str, reason: str = "Denied by user"
    ) -> str:
        with run_operation_lock(run_id):
            context, _replayed, _approval = (
                self._load_authoritative_pending_approval(
                    run_id,
                    approval_id,
                )
            )
            append_approval_denial(run_id, approval_id, reason=reason)
            append_event(
                context,
                EventType.approval_denied,
                "runtime",
                {"approval_id": approval_id, "reason": reason},
            )
            return self._halt_run(
                context, f"Approval {approval_id} denied: {reason}"
            )

    def resume(self, run_id: str, approval_id: str, token: str) -> str:
        with run_operation_lock(run_id):
            context = load_run(run_id)
            if not context:
                raise ValueError(f"Run {run_id} not found")
            try:
                from hca.runtime.replay import reconstruct_state

                replayed = reconstruct_state(run_id)
                approval = replayed.get("approval")
                if (
                    isinstance(approval, dict)
                    and approval.get("approval_id") == approval_id
                    and approval.get("status") == "denied"
                ):
                    self._current_state = context.state
                    return self._halt_run(
                        context,
                        f"Approval {approval_id} denied",
                    )

                context, replayed, _approval = (
                    self._load_authoritative_pending_approval(
                        run_id,
                        approval_id,
                        allowed_statuses=("pending", "granted"),
                    )
                )
                validation = validate_resume_approval(
                    run_id,
                    approval_id,
                    token,
                )
                if not validation["ok"]:
                    reason = validation["reason"] or "invalid_approval"
                    status = validation["resolved_status"]
                    if status == "denied":
                        return self._halt_run(
                            context, f"Approval {approval_id} denied"
                        )
                    if status == "expired":
                        self._fail_run(
                            context,
                            reason,
                            details={"approval_id": approval_id},
                        )
                    raise ValueError(reason.replace("_", " "))

                action_data = replayed.get("selected_action")
                if not isinstance(action_data, dict):
                    self._fail_run(
                        context,
                        "selected_action_unrecoverable",
                    )
                    raise ValueError(
                        "Could not reconstruct selected action from events"
                    )

                try:
                    candidate = canonicalize_action_candidate(
                        ActionCandidate.model_validate(action_data)
                    )
                except (KeyError, ToolValidationError) as exc:
                    self._fail_run(
                        context,
                        "selected_action_binding_invalid",
                        details={"approval_id": approval_id},
                    )
                    raise ValueError(
                        "Could not validate selected action from events"
                    ) from exc

                if not candidate.requires_approval:
                    raise ValueError("selected action is not approval gated")

                validation = validate_resume_approval(
                    run_id,
                    approval_id,
                    token,
                    candidate=candidate,
                )
                if not validation["ok"]:
                    reason = validation["reason"] or "invalid_approval"
                    if reason in {
                        "approved_action_mismatch",
                        "approval_binding_corrupted",
                    }:
                        self._fail_run(
                            context,
                            reason,
                            details={"approval_id": approval_id},
                            selected_action=candidate,
                        )
                    raise ValueError(reason.replace("_", " "))

                append_event(
                    context,
                    EventType.approval_granted,
                    "runtime",
                    {
                        "approval_id": approval_id,
                        "token": token,
                        "action_fingerprint": (
                            candidate.binding.action_fingerprint
                            if candidate.binding is not None
                            else None
                        ),
                    },
                )
                append_approval_consumption(
                    run_id,
                    ApprovalConsumption(
                        approval_id=approval_id,
                        token=token,
                        binding=candidate.binding,
                    ),
                )
                self._set_pending_approval(context, None)

                return self._execute_and_complete(
                    context,
                    candidate,
                    approved=True,
                    approval_id=approval_id,
                )
            except Exception as exc:
                if not isinstance(exc, ValueError):
                    self._record_unhandled_failure(context, exc)
                raise

    def _step(self, context: RunContext) -> str:
        self._set_state(context, RuntimeState.initializing)
        self._set_state(context, RuntimeState.gathering_inputs)
        workspace = Workspace(capacity=self.workspace_capacity)
        self._set_state(context, RuntimeState.proposing)
        return self._step_from_proposing(context, workspace)

    def _step_from_proposing(
        self, context: RunContext, workspace: Workspace
    ) -> str:
        for module in self.modules:
            proposal = module.propose(context.run_id)
            append_event(
                context,
                EventType.module_proposed,
                module.name,
                proposal.model_dump(mode="json"),
            )
            if context.state != RuntimeState.admitting:
                self._set_state(context, RuntimeState.admitting)
            workspace.admit(proposal.candidate_items)

        self._set_state(context, RuntimeState.broadcasting)
        broadcast(workspace, self.modules)

        self._set_state(context, RuntimeState.recurrent_update)
        run_recurrence(
            workspace,
            context=context,
            depth=1,
            modules=self.modules,
        )

        self._set_state(context, RuntimeState.action_selection)
        assessment = assess(
            workspace.items,
            failure_count=self._execution_failure_count,
            capability=capability_summary(
                workspace.items,
                failure_count=self._execution_failure_count,
            ),
        )
        append_event(
            context,
            EventType.meta_assessed,
            "meta",
            assessment.model_dump(mode="json"),
        )
        control_result = self._handle_control_signal(context, assessment)
        if control_result is not None:
            return control_result

        action_candidates = [
            item
            for item in workspace.items
            if item.kind == "action_suggestion"
        ]
        workflow_items = [
            item for item in workspace.items if item.kind == "workflow_plan"
        ]
        candidates = []
        invalid_candidates = []
        for item in action_candidates:
            try:
                candidates.append(
                    build_action_candidate(
                        item.content.get("action"),
                        item.content.get("args", {}),
                        provenance=item.provenance,
                    )
                )
            except (KeyError, ToolValidationError, ValueError) as exc:
                invalid_candidates.append(
                    {
                        "item_id": item.item_id,
                        "message": str(exc),
                    }
                )

        if invalid_candidates:
            append_event(
                context,
                EventType.report_emitted,
                "runtime",
                {
                    "reason_code": "invalid_action_candidates",
                    "issues": invalid_candidates,
                },
            )

        workflow_plans: list[WorkflowPlan] = []
        invalid_workflows = []
        for item in workflow_items:
            try:
                workflow_plans.append(
                    WorkflowPlan.model_validate(item.content)
                )
            except Exception as exc:
                invalid_workflows.append(
                    {
                        "item_id": item.item_id,
                        "message": str(exc),
                    }
                )

        if invalid_workflows:
            append_event(
                context,
                EventType.report_emitted,
                "runtime",
                {
                    "reason_code": "invalid_workflow_plans",
                    "issues": invalid_workflows,
                },
            )

        if not candidates and not workflow_plans:
            return self._fail_run(
                context,
                "no_actionable_candidates",
                workspace=workspace,
            )

        if workflow_plans:
            scored_workflows = score_workflow_plans(workflow_plans)
            best_workflow = None
            best_workflow_score: Optional[Dict[str, float]] = None
            best_candidate = None
            for workflow, workflow_score in scored_workflows:
                if not workflow.steps:
                    continue
                try:
                    candidate = self._candidate_for_workflow_step(
                        context,
                        workflow,
                        workflow.steps[0],
                        provenance=[f"workflow_plan:{workflow.workflow_id}"],
                        step_history=[],
                    )
                except (KeyError, ToolValidationError, ValueError) as exc:
                    invalid_workflows.append(
                        {
                            "workflow_id": workflow.workflow_id,
                            "message": str(exc),
                        }
                    )
                    continue
                best_workflow = workflow
                best_workflow_score = workflow_score
                best_candidate = candidate
                break

            if best_workflow is not None and best_candidate is not None:
                self._activate_workflow(
                    context,
                    best_workflow,
                    score=best_workflow_score,
                )
                self._select_action(context, best_candidate)
                if best_candidate.requires_approval:
                    return self._request_approval(
                        context,
                        best_candidate,
                        workspace=workspace,
                    )

                self._set_pending_approval(context, None)
                return self._execute_and_complete(
                    context,
                    best_candidate,
                    approved=False,
                    workspace=workspace,
                )

        if not candidates:
            return self._fail_run(
                context,
                "no_valid_action_candidates",
                workspace=workspace,
            )

        scored = score_actions(candidates)
        for candidate, score in scored:
            append_event(
                context,
                EventType.action_scored,
                "runtime",
                {
                    "action_id": candidate.action_id,
                    "kind": candidate.kind,
                    "score": score,
                },
            )

        signal = assessment.recommended_transition
        selected_index = 0
        if signal == ControlSignal.backtrack and len(scored) > 1:
            selected_index = 1
            append_event(
                context,
                EventType.report_emitted,
                "runtime",
                {"reason_code": "backtrack", "selected_rank": 2},
            )

        best_candidate, _ = scored[selected_index]
        self._select_action(context, best_candidate)

        if best_candidate.requires_approval:
            return self._request_approval(
                context,
                best_candidate,
                workspace=workspace,
            )

        self._set_pending_approval(context, None)
        return self._execute_and_complete(
            context,
            best_candidate,
            approved=False,
            workspace=workspace,
        )

    def _execute_and_complete(
        self,
        context: RunContext,
        candidate: ActionCandidate,
        approved: bool = False,
        approval_id: Optional[str] = None,
        workspace: Optional[Workspace] = None,
    ) -> str:
        if context.state != RuntimeState.executing:
            self._set_state(
                context,
                RuntimeState.executing,
                {"tool": candidate.kind, "action_id": candidate.action_id},
            )
        if (
            context.active_workflow is not None
            and candidate.workflow_id == context.active_workflow.workflow_id
            and candidate.workflow_step_id is not None
        ):
            step = next(
                (
                    current
                    for current in context.active_workflow.steps
                    if current.step_id == candidate.workflow_step_id
                ),
                None,
            )
            append_event(
                context,
                EventType.workflow_step_started,
                "runtime",
                {
                    "workflow_id": candidate.workflow_id,
                    "workflow_step_id": candidate.workflow_step_id,
                    "step_key": step.step_key if step is not None else None,
                    "tool_name": candidate.kind,
                    "action_id": candidate.action_id,
                    "approval_id": approval_id,
                },
            )
        append_event(
            context,
            EventType.execution_started,
            "executor",
            {
                "tool": candidate.kind,
                "action_id": candidate.action_id,
                "approved": approved,
                "approval_id": approval_id,
                "arguments": candidate.arguments,
                "action_fingerprint": (
                    candidate.binding.action_fingerprint
                    if candidate.binding is not None
                    else None
                ),
            },
        )

        receipt = self.executor.execute(
            context.run_id,
            candidate,
            approved=approved,
            approval_id=approval_id,
        )
        receipt_payload = receipt.model_dump(mode="json")
        append_event(
            context,
            EventType.execution_finished,
            "executor",
            receipt_payload,
        )

        self._set_state(context, RuntimeState.observing)
        self._set_state(context, RuntimeState.memory_commit)
        try:
            self._record_execution_memory(
                context,
                candidate,
                receipt_payload,
            )
        except Exception as exc:
            self._execution_failure_count += 1
            return self._fail_run(
                context,
                "memory_commit_failed",
                details={
                    "failure_count": self._execution_failure_count,
                    "error_type": exc.__class__.__name__,
                    "error": str(exc),
                },
                workspace=workspace,
                selected_action=candidate,
                latest_receipt_id=receipt.receipt_id,
            )

        if (
            context.active_workflow is not None
            and candidate.workflow_id == context.active_workflow.workflow_id
        ):
            return self._continue_workflow(
                context,
                candidate,
                receipt_payload,
                workspace=workspace,
            )

        if receipt.status == ReceiptStatus.success:
            self._set_state(context, RuntimeState.reporting)
            append_event(
                context,
                EventType.report_emitted,
                "runtime",
                {
                    "action_id": candidate.action_id,
                    "status": receipt.status.value,
                    "failure_count": self._execution_failure_count,
                },
            )
            self._set_state(context, RuntimeState.completed)
            append_event(
                context,
                EventType.run_completed,
                "runtime",
                {"receipt_id": receipt.receipt_id},
            )
        else:
            self._execution_failure_count += 1
            append_event(
                context,
                EventType.report_emitted,
                "runtime",
                {
                    "reason_code": "failure_loop",
                    "failure_count": self._execution_failure_count,
                },
            )
            if workspace is None:
                return self._fail_run(
                    context,
                    "execution_failure",
                    details={
                        "failure_count": self._execution_failure_count,
                        "status": receipt.status.value,
                    },
                    selected_action=candidate,
                    latest_receipt_id=receipt.receipt_id,
                )
            if self._execution_failure_count > 2:
                return self._fail_run(
                    context,
                    "repeated_execution_failures",
                    details={
                        "failure_count": self._execution_failure_count,
                        "status": receipt.status.value,
                    },
                    workspace=workspace,
                    selected_action=candidate,
                    latest_receipt_id=receipt.receipt_id,
                )
            else:
                append_event(
                    context,
                    EventType.report_emitted,
                    "runtime",
                    {
                        "action_id": candidate.action_id,
                        "status": receipt.status.value,
                        "failure_count": self._execution_failure_count,
                    },
                )
                self._set_state(
                    context,
                    RuntimeState.proposing,
                    {
                        "reason": "execution_failure_retry",
                        "failure_count": self._execution_failure_count,
                    },
                )
                self._write_snapshot(
                    context,
                    workspace or [],
                    selected_action=candidate,
                    latest_receipt_id=receipt.receipt_id,
                )
                return self._step_from_proposing(
                    context,
                    Workspace(capacity=self.workspace_capacity),
                )

        self._write_snapshot(
            context,
            workspace or [],
            selected_action=candidate,
            latest_receipt_id=receipt.receipt_id,
        )
        return context.run_id
