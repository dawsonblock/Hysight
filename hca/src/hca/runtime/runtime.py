"""Runtime orchestrator for the hybrid cognitive agent."""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any, Dict, Optional

from hca.common.enums import (
    ActionClass,
    ControlSignal,
    EventType,
    MemoryType,
    ReceiptStatus,
    RuntimeState,
)
from hca.common.time import utc_now
from hca.common.types import (
    ActionCandidate,
    ApprovalConsumption,
    MetaAssessment,
    ApprovalRequest,
    MemoryRecord,
    RunContext,
)
from hca.executor.approvals import validate_resume_approval
from hca.executor.executor import Executor
from hca.memory.episodic_store import EpisodicStore
from hca.meta.monitor import assess
from hca.meta.self_model import capability_summary
from hca.modules import Planner, Critic, TextPerception, ToolReasoner
from hca.prediction.action_scoring import score_actions
from hca.runtime.snapshots import build_runtime_snapshot
from hca.runtime.state_machine import assert_transition
from hca.storage import (
    append_consumption as append_approval_consumption,
    append_denial as append_approval_denial,
    append_event,
    append_snapshot,
    append_request as append_approval_request,
    load_run,
    save_run,
)
from hca.workspace.broadcast import broadcast
from hca.workspace.recurrence import run_recurrence
from hca.workspace.workspace import Workspace


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

    def _record_execution_memory(
        self,
        context: RunContext,
        candidate: ActionCandidate,
        receipt_payload: Dict[str, Any],
    ) -> None:
        record = MemoryRecord(
            memory_type=MemoryType.episodic,
            run_id=context.run_id,
            subject=candidate.kind,
            content={
                "action_id": candidate.action_id,
                "action_kind": candidate.kind,
                "arguments": candidate.arguments,
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
        EpisodicStore(context.run_id).append(record)
        append_event(
            context,
            EventType.memory_written,
            "runtime",
            {
                "record_id": record.record_id,
                "memory_type": MemoryType.episodic.value,
                "subject": record.subject,
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

        append_event(
            context,
            EventType.approval_granted,
            "runtime",
            {"approval_id": approval_id, "token": token},
        )
        append_approval_consumption(
            run_id,
            ApprovalConsumption(approval_id=approval_id, token=token),
        )
        context.pending_approval_id = None
        self._persist_context(context)

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

        candidate = ActionCandidate.model_validate(action_data)
        return self._execute_and_complete(context, candidate, approved=True)

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
        if not action_candidates:
            self._set_state(
                context,
                RuntimeState.failed,
                {"reason": "no_actionable_candidates"},
            )
            self._write_snapshot(context, workspace)
            return context.run_id

        candidates = [
            ActionCandidate(
                kind=item.content.get("action"),
                arguments=item.content.get("args", {}),
                requires_approval=item.content.get("action") != "echo",
                provenance=item.provenance,
            )
            for item in action_candidates
        ]
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
        append_event(
            context,
            EventType.action_selected,
            "runtime",
            best_candidate.model_dump(mode="json"),
        )

        if best_candidate.requires_approval:
            approval_id = str(uuid.uuid4())
            request = ApprovalRequest(
                approval_id=approval_id,
                run_id=context.run_id,
                action_id=best_candidate.action_id,
                action_class=(
                    ActionClass.high
                    if best_candidate.kind == "write_artifact"
                    else ActionClass.medium
                ),
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
                    "action_id": best_candidate.action_id,
                    "action_kind": best_candidate.kind,
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
                workspace,
                selected_action=best_candidate,
            )
            return context.run_id

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
        workspace: Optional[Workspace] = None,
    ) -> str:
        if context.state != RuntimeState.executing:
            self._set_state(
                context,
                RuntimeState.executing,
                {"tool": candidate.kind, "action_id": candidate.action_id},
            )
        append_event(
            context,
            EventType.execution_started,
            "executor",
            {
                "tool": candidate.kind,
                "action_id": candidate.action_id,
                "approved": approved,
                "arguments": candidate.arguments,
            },
        )

        receipt = self.executor.execute(
            context.run_id, candidate, approved=approved
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
        self._record_execution_memory(context, candidate, receipt_payload)

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
