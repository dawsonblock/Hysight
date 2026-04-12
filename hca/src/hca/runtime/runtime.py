"""Runtime orchestrator for the hybrid cognitive agent."""

from __future__ import annotations

import uuid
from datetime import timedelta
from functools import lru_cache
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
    append_denial as append_approval_denial,
    append_event,
    append_request as append_approval_request,
    append_snapshot,
    load_run,
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
        context.workflow_budget = WorkflowBudget(
            max_steps=max(workflow.max_steps, len(workflow.steps)),
            consumed_steps=0,
        )
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
        context.pending_approval_id = approval_id
        self._persist_context(context)
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
            self._set_state(
                context,
                RuntimeState.failed,
                {
                    "reason": "workflow_step_failed",
                    "workflow_id": workflow.workflow_id,
                    "workflow_step_id": candidate.workflow_step_id,
                    "failure_count": self._execution_failure_count,
                },
            )
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
                EventType.run_failed,
                "runtime",
                {
                    "receipt_id": receipt_payload.get("receipt_id"),
                    "failure_count": self._execution_failure_count,
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
                },
            )
            append_event(
                context,
                EventType.workflow_terminated,
                "runtime",
                {
                    "workflow_id": workflow.workflow_id,
                    "reason": "budget_exhausted",
                },
            )
            self._set_state(
                context,
                RuntimeState.failed,
                {
                    "reason": "workflow_budget_exhausted",
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
            self._set_state(
                context,
                RuntimeState.failed,
                {
                    "reason": "workflow_next_step_unbuildable",
                    "workflow_id": workflow.workflow_id,
                    "workflow_step_id": next_step.step_id,
                },
            )
            self._write_snapshot(
                context,
                workspace or [],
                selected_action=candidate,
                latest_receipt_id=receipt_payload.get("receipt_id"),
            )
            return context.run_id
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
        try:
            EpisodicStore(context.run_id).append(record)
        except Exception as exc:
            append_event(
                context,
                EventType.report_emitted,
                "runtime",
                {
                    "reason_code": "episodic_memory_write_failed",
                    "action_id": candidate.action_id,
                    "error_type": exc.__class__.__name__,
                    "error": str(exc),
                },
            )
            raise

        episodic_payload = {
            "record_id": record.record_id,
            "memory_type": MemoryType.episodic.value,
            "subject": record.subject,
            "action_id": candidate.action_id,
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
                append_event(
                    context,
                    EventType.external_memory_written,
                    "runtime",
                    {
                        "action_id": candidate.action_id,
                        "subject": record.subject,
                        "memory_id": memory_id,
                    },
                )
            except Exception as exc:
                append_event(
                    context,
                    EventType.external_memory_write_failed,
                    "runtime",
                    {
                        "action_id": candidate.action_id,
                        "subject": record.subject,
                        "error_type": exc.__class__.__name__,
                        "error": str(exc),
                    },
                )

        append_event(
            context,
            EventType.memory_written,
            "runtime",
            episodic_payload,
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

    def run(self, goal: str, user_id: str | None = None) -> str:
        context = self.create_run(goal, user_id)
        self._current_state = RuntimeState.created
        self._remaining_replan = self.replan_budget
        self._execution_failure_count = 0
        return self._step(context)

    def deny_approval(
        self, run_id: str, approval_id: str, reason: str = "Denied by user"
    ) -> str:
        context = load_run(run_id)
        if not context:
            raise ValueError(f"Run {run_id} not found")

        self._current_state = context.state
        context.pending_approval_id = approval_id
        self._persist_context(context)
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
        context = load_run(run_id)
        if not context:
            raise ValueError(f"Run {run_id} not found")

        self._current_state = context.state
        validation = validate_resume_approval(run_id, approval_id, token)
        if not validation["ok"]:
            reason = validation["reason"] or "invalid_approval"
            status = validation["resolved_status"]
            if status == "denied":
                return self._halt_run(
                    context, f"Approval {approval_id} denied"
                )
            if status == "expired":
                self._set_state(
                    context,
                    RuntimeState.failed,
                    {"reason": reason, "approval_id": approval_id},
                )
                self._write_snapshot(context, [], None)
            raise ValueError(reason.replace("_", " "))

        from hca.runtime.replay import reconstruct_state

        replayed = reconstruct_state(run_id)
        action_data = replayed.get("selected_action")
        if not isinstance(action_data, dict):
            self._set_state(
                context,
                RuntimeState.failed,
                {"reason": "selected_action_unrecoverable"},
            )
            self._write_snapshot(context, [], None)
            raise ValueError(
                "Could not reconstruct selected action from events"
            )

        try:
            candidate = canonicalize_action_candidate(
                ActionCandidate.model_validate(action_data)
            )
        except (KeyError, ToolValidationError) as exc:
            self._set_state(
                context,
                RuntimeState.failed,
                {
                    "reason": "selected_action_binding_invalid",
                    "approval_id": approval_id,
                },
            )
            self._write_snapshot(context, [], None)
            raise ValueError(
                "Could not validate selected action from events"
            ) from exc

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
                self._set_state(
                    context,
                    RuntimeState.failed,
                    {"reason": reason, "approval_id": approval_id},
                )
                self._write_snapshot(context, [], candidate)
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
        context.pending_approval_id = None
        self._persist_context(context)

        return self._execute_and_complete(
            context,
            candidate,
            approved=True,
            approval_id=approval_id,
        )

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
            self._set_state(
                context,
                RuntimeState.failed,
                {"reason": "no_actionable_candidates"},
            )
            self._write_snapshot(context, workspace)
            return context.run_id

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

                context.pending_approval_id = None
                self._persist_context(context)
                return self._execute_and_complete(
                    context,
                    best_candidate,
                    approved=False,
                    workspace=workspace,
                )

        if not candidates:
            self._set_state(
                context,
                RuntimeState.failed,
                {"reason": "no_valid_action_candidates"},
            )
            self._write_snapshot(context, workspace)
            return context.run_id

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

        context.pending_approval_id = None
        self._persist_context(context)
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
            append_event(
                context,
                EventType.report_emitted,
                "runtime",
                {
                    "reason_code": "memory_commit_failed",
                    "action_id": candidate.action_id,
                    "failure_count": self._execution_failure_count,
                    "error_type": exc.__class__.__name__,
                    "error": str(exc),
                },
            )
            self._set_state(
                context,
                RuntimeState.failed,
                {
                    "reason": "memory_commit_failed",
                    "failure_count": self._execution_failure_count,
                },
            )
            self._write_snapshot(
                context,
                workspace or [],
                selected_action=candidate,
                latest_receipt_id=receipt.receipt_id,
            )
            return context.run_id

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
                self._set_state(
                    context,
                    RuntimeState.failed,
                    {
                        "reason": "execution_failure",
                        "failure_count": self._execution_failure_count,
                    },
                )
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
                append_event(
                    context,
                    EventType.run_failed,
                    "runtime",
                    {
                        "receipt_id": receipt.receipt_id,
                        "failure_count": self._execution_failure_count,
                    },
                )
                self._write_snapshot(
                    context,
                    [],
                    selected_action=candidate,
                    latest_receipt_id=receipt.receipt_id,
                )
                return context.run_id
            if self._execution_failure_count > 2:
                self._set_state(
                    context,
                    RuntimeState.failed,
                    {
                        "reason": "repeated_execution_failures",
                        "failure_count": self._execution_failure_count,
                    },
                )
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
                append_event(
                    context,
                    EventType.run_failed,
                    "runtime",
                    {
                        "receipt_id": receipt.receipt_id,
                        "failure_count": self._execution_failure_count,
                    },
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
