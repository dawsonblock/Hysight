"""Bounded autonomy supervisor.

This supervisor never executes tools directly. Instead it converts accepted
inbox/schedule triggers into ordinary ``Runtime.create_autonomous_run(...)``
invocations, attaches autonomy metadata to the run, writes autonomy events to
the run's existing event log, checkpoints progress, and observes subsequent
state changes through the existing replay/event log.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Protocol

from pydantic import BaseModel

from hca.autonomy import storage
from hca.autonomy.checkpoint import (
    AutonomyBudgetState,
    AutonomyCheckpoint,
    AutonomyKillSwitch,
    AutonomyRunLink,
)
from hca.autonomy.evaluator import EvaluatorReport, evaluate as evaluator_evaluate
from hca.autonomy.policy import AutonomyPolicy, PolicyDecision
from hca.autonomy.triggers import (
    AutonomyAgent,
    AutonomyInboxItem,
    AutonomySchedule,
    AutonomyTrigger,
)
from hca.common.enums import (
    AgentStatus,
    CheckpointStatus,
    EvaluatorDecision,
    EventType,
    Idempotency,
    InboxStatus,
    RuntimeState,
    TriggerStatus,
    TriggerType,
)
from hca.common.time import utc_now
from hca.common.types import RunContext
from hca.storage.event_log import append_event, read_events
from hca.storage.runs import load_run


class _RuntimeProtocol(Protocol):
    def create_autonomous_run(
        self,
        goal: str,
        *,
        user_id: str | None = None,
        autonomy_agent_id: str,
        autonomy_trigger_id: str,
        autonomy_mode: str,
    ) -> RunContext:
        ...


class SupervisorStatus(BaseModel):
    enabled: bool
    running: bool
    loop_running: bool = False
    active_agents: int
    active_runs: int
    pending_triggers: int
    kill_switch_active: bool = False
    kill_switch_reason: Optional[str] = None
    kill_switch_set_at: Optional[datetime] = None
    last_tick_at: Optional[datetime] = None
    last_error: Optional[str] = None


@dataclass
class SupervisorDecision:
    decision: str
    reason: Optional[str] = None
    evidence: Dict[str, Any] = field(default_factory=dict)


class AutonomySupervisor:
    """Bounded autonomy supervisor.

    ``tick()`` performs one synchronous poll cycle. Tests drive the supervisor
    explicitly through ``tick()`` so there is no hidden background executor.
    """

    def __init__(
        self,
        *,
        runtime: Optional[_RuntimeProtocol] = None,
        enabled: bool = True,
    ) -> None:
        self._runtime_factory = runtime
        self._enabled = enabled
        self._running = False
        self._last_tick_at: Optional[datetime] = None
        self._last_error: Optional[str] = None
        self._lock = threading.RLock()
        # Background loop (optional; tests drive via tick() directly).
        self._loop_thread: Optional[threading.Thread] = None
        self._loop_stop: Optional[threading.Event] = None
        self._loop_interval_seconds: float = 5.0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        self._running = True

    def stop(self) -> None:
        self._running = False

    def start_loop(self, *, interval_seconds: float = 5.0) -> bool:
        """Start a single background polling loop.

        Returns True if a new loop was started, False if one was already
        running. Safe to call repeatedly — single-instance guarded.
        """
        with self._lock:
            if self._loop_thread is not None and self._loop_thread.is_alive():
                return False
            self._loop_interval_seconds = max(0.1, float(interval_seconds))
            self._loop_stop = threading.Event()
            self._running = True
            thread = threading.Thread(
                target=self._run_loop,
                name="autonomy-supervisor-loop",
                daemon=True,
            )
            self._loop_thread = thread
            thread.start()
            storage.append_autonomy_audit(
                {
                    "event": EventType.autonomy_supervisor_started.value,
                    "interval_seconds": self._loop_interval_seconds,
                }
            )
            return True

    def stop_loop(self, *, timeout_seconds: float = 5.0) -> bool:
        """Stop the background loop (if running). Returns True if stopped."""
        with self._lock:
            thread = self._loop_thread
            stop_event = self._loop_stop
            self._loop_thread = None
            self._loop_stop = None
        if thread is None or stop_event is None:
            return False
        stop_event.set()
        thread.join(timeout=timeout_seconds)
        storage.append_autonomy_audit(
            {
                "event": EventType.autonomy_supervisor_stopped.value,
                "joined_cleanly": not thread.is_alive(),
            }
        )
        self._running = False
        return not thread.is_alive()

    def _run_loop(self) -> None:
        stop_event = self._loop_stop
        if stop_event is None:
            return
        while not stop_event.is_set():
            try:
                self.tick()
            except Exception as exc:  # pragma: no cover - defensive
                self._last_error = f"{exc.__class__.__name__}: {exc}"
            # Sleep in small slices so stop_loop returns promptly.
            stop_event.wait(timeout=self._loop_interval_seconds)

    @property
    def loop_running(self) -> bool:
        thread = self._loop_thread
        return bool(thread is not None and thread.is_alive())

    def _get_runtime(self) -> _RuntimeProtocol:
        if self._runtime_factory is not None:
            return self._runtime_factory
        from hca.runtime.runtime import Runtime

        self._runtime_factory = Runtime()
        return self._runtime_factory

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def status(self) -> SupervisorStatus:
        with self._lock:
            agents = storage.list_agents()
            active_agents = sum(
                1 for agent in agents if agent.status == AgentStatus.active
            )
            active_runs = len(storage.list_active_autonomy_runs())
            pending = len(storage.list_inbox_items(status=InboxStatus.pending))
            kill_switch = storage.load_kill_switch()
            return SupervisorStatus(
                enabled=self._enabled,
                running=self._running,
                loop_running=self.loop_running,
                active_agents=active_agents,
                active_runs=active_runs,
                pending_triggers=pending,
                kill_switch_active=kill_switch.active,
                kill_switch_reason=kill_switch.reason,
                kill_switch_set_at=kill_switch.set_at,
                last_tick_at=self._last_tick_at,
                last_error=self._last_error,
            )

    # ------------------------------------------------------------------
    # Kill switch
    # ------------------------------------------------------------------

    def set_kill_switch(
        self,
        *,
        active: bool,
        reason: Optional[str] = None,
        set_by: Optional[str] = None,
    ) -> AutonomyKillSwitch:
        record = storage.set_kill_switch(
            active=active, reason=reason, set_by=set_by
        )
        audit_event = (
            EventType.autonomy_kill_switch_enabled.value
            if active
            else EventType.autonomy_kill_switch_cleared.value
        )
        storage.append_autonomy_audit(
            {
                "event": audit_event,
                "reason": reason,
                "set_by": set_by,
            }
        )
        return record

    # ------------------------------------------------------------------
    # Agent controls
    # ------------------------------------------------------------------

    def pause_agent(self, agent_id: str) -> AutonomyAgent:
        return storage.set_agent_status(agent_id, AgentStatus.paused)

    def resume_agent(self, agent_id: str) -> AutonomyAgent:
        return storage.set_agent_status(agent_id, AgentStatus.active)

    def stop_agent(self, agent_id: str) -> AutonomyAgent:
        return storage.set_agent_status(agent_id, AgentStatus.stopped)

    # ------------------------------------------------------------------
    # Poll / accept / launch
    # ------------------------------------------------------------------

    def poll_triggers(
        self, *, now: Optional[datetime] = None
    ) -> List[AutonomyTrigger]:
        reference = now or utc_now()
        triggers: List[AutonomyTrigger] = []
        agents_by_id = {agent.agent_id: agent for agent in storage.list_agents()}

        for agent in agents_by_id.values():
            if agent.status != AgentStatus.active:
                continue
            inbox_item = storage.claim_inbox_item(agent.agent_id)
            if inbox_item is not None:
                triggers.append(
                    AutonomyTrigger(
                        agent_id=agent.agent_id,
                        trigger_type=TriggerType.inbox,
                        goal=inbox_item.goal,
                        payload={
                            "inbox_item_id": inbox_item.item_id,
                            **dict(inbox_item.payload),
                        },
                        dedupe_key=f"inbox:{inbox_item.item_id}",
                    )
                )

        for schedule in storage.list_due_schedules(reference):
            agent = agents_by_id.get(schedule.agent_id)
            if agent is None or agent.status != AgentStatus.active:
                continue
            bucket = int(reference.timestamp() // max(schedule.interval_seconds, 1))
            triggers.append(
                AutonomyTrigger(
                    agent_id=agent.agent_id,
                    trigger_type=TriggerType.schedule,
                    goal=schedule.goal_override or f"schedule:{schedule.schedule_id}",
                    payload={
                        "schedule_id": schedule.schedule_id,
                        **dict(schedule.payload),
                    },
                    dedupe_key=f"schedule:{schedule.schedule_id}:{bucket}",
                    not_before=reference,
                )
            )
            storage.mark_schedule_fired(schedule.schedule_id, reference)

        return triggers

    def accept_trigger(self, trigger: AutonomyTrigger) -> PolicyDecision:
        agent = storage.get_agent(trigger.agent_id)
        storage.append_autonomy_audit(
            {
                "event": EventType.autonomy_trigger_received.value,
                "trigger_id": trigger.trigger_id,
                "agent_id": trigger.agent_id,
                "trigger_type": trigger.trigger_type.value,
                "dedupe_key": trigger.dedupe_key,
            }
        )

        # Hard gate 1: kill switch blocks all new autonomy.
        kill_switch = storage.load_kill_switch()
        if kill_switch.active:
            decision = PolicyDecision(
                allowed=False,
                reason="kill_switch_active",
                evidence={"kill_switch_reason": kill_switch.reason},
            )
            storage.append_autonomy_audit(
                {
                    "event": EventType.autonomy_trigger_rejected.value,
                    "trigger_id": trigger.trigger_id,
                    "agent_id": trigger.agent_id,
                    "reason": decision.reason,
                    "evidence": decision.evidence,
                }
            )
            return decision

        # Hard gate 2: dedupe — if the same dedupe_key already produced a
        # linked run, reject. Survives restart because dedupe state is
        # file-backed.
        if trigger.dedupe_key:
            existing = storage.find_dedupe(trigger.dedupe_key)
            if existing is not None:
                decision = PolicyDecision(
                    allowed=False,
                    reason="duplicate_dedupe_key",
                    evidence={
                        "dedupe_key": trigger.dedupe_key,
                        "existing_trigger_id": existing.get("trigger_id"),
                        "existing_run_id": existing.get("run_id"),
                    },
                )
                storage.append_autonomy_audit(
                    {
                        "event": EventType.autonomy_trigger_deduped.value,
                        "trigger_id": trigger.trigger_id,
                        "agent_id": trigger.agent_id,
                        "dedupe_key": trigger.dedupe_key,
                        "existing_trigger_id": existing.get("trigger_id"),
                        "existing_run_id": existing.get("run_id"),
                    }
                )
                return decision

        if agent is None:
            decision = PolicyDecision(
                allowed=False,
                reason="agent_not_found",
                evidence={"agent_id": trigger.agent_id},
            )
        elif agent.status != AgentStatus.active:
            decision = PolicyDecision(
                allowed=False,
                reason=f"agent_status_{agent.status.value}",
                evidence={"agent_id": agent.agent_id},
            )
        else:
            decision = agent.policy.check_trigger(trigger.trigger_type.value)

        audit_event = (
            EventType.autonomy_trigger_accepted.value
            if decision.allowed
            else EventType.autonomy_trigger_rejected.value
        )
        storage.append_autonomy_audit(
            {
                "event": audit_event,
                "trigger_id": trigger.trigger_id,
                "agent_id": trigger.agent_id,
                "reason": decision.reason,
                "evidence": decision.evidence,
            }
        )
        return decision

    def launch_run(self, trigger: AutonomyTrigger) -> AutonomyRunLink:
        agent = storage.get_agent(trigger.agent_id)
        if agent is None:
            raise LookupError(f"agent {trigger.agent_id} not found")

        runtime = self._get_runtime()
        context = runtime.create_autonomous_run(
            trigger.goal,
            autonomy_agent_id=agent.agent_id,
            autonomy_trigger_id=trigger.trigger_id,
            autonomy_mode=agent.mode.value,
        )

        append_event(
            context,
            EventType.autonomy_run_launched,
            "autonomy",
            {
                "trigger_id": trigger.trigger_id,
                "trigger_type": trigger.trigger_type.value,
                "agent_id": agent.agent_id,
                "autonomy_mode": agent.mode.value,
                "dedupe_key": trigger.dedupe_key,
            },
        )

        # Durable ledger update: +1 launched, +1 active, run started.
        ledger = storage.update_budget_ledger(
            agent.agent_id,
            launched_runs_delta=1,
            active_runs_delta=1,
            run_started=True,
        )
        append_event(
            context,
            EventType.autonomy_budget_updated,
            "autonomy",
            {
                "launched_runs_total": ledger.launched_runs_total,
                "active_runs": ledger.active_runs,
            },
        )

        budget_snapshot = AutonomyBudgetState(
            runs_launched=ledger.launched_runs_total,
            parallel_runs=ledger.active_runs,
            run_started_at=utc_now(),
        ).model_dump(mode="json")

        kill_switch = storage.load_kill_switch()
        checkpoint = AutonomyCheckpoint(
            agent_id=agent.agent_id,
            trigger_id=trigger.trigger_id,
            run_id=context.run_id,
            status=CheckpointStatus.launched,
            attempt=1,
            last_state=context.state.value,
            resume_allowed=True,
            safe_to_continue=True,
            kill_switch_observed=kill_switch.active,
            idempotency=Idempotency.unknown,
            dedupe_key=trigger.dedupe_key,
            budget_snapshot=budget_snapshot,
        )
        storage.save_checkpoint(checkpoint)
        append_event(
            context,
            EventType.autonomy_checkpoint_written,
            "autonomy",
            {
                "trigger_id": trigger.trigger_id,
                "status": checkpoint.status.value,
                "attempt": checkpoint.attempt,
                "safe_to_continue": checkpoint.safe_to_continue,
            },
        )

        # Durable dedupe record: survives restart so the same trigger cannot
        # be relaunched by a later tick or a restarted supervisor.
        if trigger.dedupe_key:
            storage.record_dedupe(
                dedupe_key=trigger.dedupe_key,
                trigger_id=trigger.trigger_id,
                agent_id=agent.agent_id,
                run_id=context.run_id,
            )

        inbox_item_id = trigger.payload.get("inbox_item_id")
        if isinstance(inbox_item_id, str):
            storage.complete_inbox_item(inbox_item_id)

        return AutonomyRunLink(
            agent_id=agent.agent_id,
            trigger_id=trigger.trigger_id,
            run_id=context.run_id,
        )

    # ------------------------------------------------------------------
    # Observation / decisions
    # ------------------------------------------------------------------

    def observe_run(self, run_id: str) -> Optional[AutonomyCheckpoint]:
        context = load_run(run_id)
        if context is None:
            return None
        if not context.autonomy_agent_id or not context.autonomy_trigger_id:
            return None

        existing = storage.load_checkpoint(
            context.autonomy_agent_id, context.autonomy_trigger_id
        )
        if existing is None:
            return None

        events, _ = read_events(run_id)
        agent = storage.get_agent(context.autonomy_agent_id)
        policy = agent.policy if agent is not None else AutonomyPolicy()
        ledger = storage.get_budget_ledger(context.autonomy_agent_id)
        kill_switch = storage.load_kill_switch()

        report = evaluator_evaluate(
            context=context,
            events=events,
            policy=policy,
            ledger=ledger,
            kill_switch=kill_switch,
            idempotency=existing.idempotency,
        )

        decision_value = report.decision.value
        append_event(
            context,
            EventType.autonomy_evaluator_decided,
            "autonomy",
            {
                "decision": decision_value,
                "reason": report.reason,
                "safe_to_continue": report.safe_to_continue,
                "idempotency": report.idempotency.value,
            },
        )

        # Map evaluator decision → checkpoint status.
        if report.decision == EvaluatorDecision.escalate:
            new_status = CheckpointStatus.awaiting_approval
        elif report.decision in (
            EvaluatorDecision.stop_budget,
            EvaluatorDecision.stop_deadman,
            EvaluatorDecision.stop_killed,
        ):
            new_status = CheckpointStatus.stopped
        elif report.decision == EvaluatorDecision.retry:
            new_status = CheckpointStatus.retry_scheduled
        elif report.decision == EvaluatorDecision.complete:
            new_status = CheckpointStatus.completed
        elif context.state == RuntimeState.failed:
            new_status = CheckpointStatus.failed
        else:
            new_status = CheckpointStatus.observing

        # Durable ledger update on terminal transitions.
        if new_status in (
            CheckpointStatus.completed,
            CheckpointStatus.failed,
            CheckpointStatus.stopped,
        ) and existing.status not in (
            CheckpointStatus.completed,
            CheckpointStatus.failed,
            CheckpointStatus.stopped,
        ):
            storage.update_budget_ledger(
                context.autonomy_agent_id,
                active_runs_delta=-1,
                run_completed=True,
                budget_breach=report.decision == EvaluatorDecision.stop_budget,
            )

        resume_allowed = (
            report.decision
            not in (
                EvaluatorDecision.stop_budget,
                EvaluatorDecision.stop_deadman,
                EvaluatorDecision.stop_killed,
            )
            and report.safe_to_continue
        )

        updated = AutonomyCheckpoint(
            agent_id=existing.agent_id,
            trigger_id=existing.trigger_id,
            run_id=existing.run_id,
            status=new_status,
            attempt=existing.attempt,
            last_event_id=(
                events[-1].get("event_id") if events else existing.last_event_id
            ),
            last_state=context.state.value,
            last_decision=decision_value,
            resume_allowed=resume_allowed,
            safe_to_continue=report.safe_to_continue,
            kill_switch_observed=kill_switch.active,
            idempotency=report.idempotency,
            dedupe_key=existing.dedupe_key,
            budget_snapshot=existing.budget_snapshot,
        )
        storage.save_checkpoint(updated)

        append_event(
            context,
            EventType.autonomy_run_observed,
            "autonomy",
            {
                "decision": decision_value,
                "reason": report.reason,
                "run_state": context.state.value,
            },
        )

        if report.decision == EvaluatorDecision.escalate:
            append_event(
                context,
                EventType.autonomy_escalation_requested,
                "autonomy",
                {
                    "reason": report.reason,
                    "run_state": context.state.value,
                    "evidence": report.evidence,
                },
            )
        elif report.decision == EvaluatorDecision.stop_budget:
            append_event(
                context,
                EventType.autonomy_budget_exceeded,
                "autonomy",
                {"reason": report.reason, "evidence": report.evidence},
            )
            append_event(
                context,
                EventType.autonomy_stopped,
                "autonomy",
                {"reason": report.reason},
            )
        elif report.decision == EvaluatorDecision.stop_deadman:
            append_event(
                context,
                EventType.autonomy_stopped,
                "autonomy",
                {"reason": report.reason, "evidence": report.evidence},
            )
        elif report.decision == EvaluatorDecision.stop_killed:
            append_event(
                context,
                EventType.autonomy_stopped,
                "autonomy",
                {"reason": report.reason, "evidence": report.evidence},
            )
        elif report.decision == EvaluatorDecision.retry:
            # Block retry if non-idempotent and not safe.
            if (
                report.idempotency == Idempotency.non_idempotent
                or not report.safe_to_continue
            ):
                append_event(
                    context,
                    EventType.autonomy_continuation_blocked_non_idempotent,
                    "autonomy",
                    {
                        "reason": "non_idempotent_retry_blocked",
                        "idempotency": report.idempotency.value,
                    },
                )
            else:
                append_event(
                    context,
                    EventType.autonomy_retry_scheduled,
                    "autonomy",
                    {"reason": report.reason, "evidence": report.evidence},
                )

        return updated

    def decide_next_action(
        self,
        context: RunContext,
        events: List[Dict[str, Any]],
    ) -> SupervisorDecision:
        agent = (
            storage.get_agent(context.autonomy_agent_id)
            if context.autonomy_agent_id
            else None
        )
        if agent is None:
            return SupervisorDecision(decision="continue_observe")

        step_events = sum(
            1
            for event in events
            if event.get("event_type")
            in {
                EventType.execution_started.value,
                EventType.workflow_step_started.value,
            }
        )
        retry_events = sum(
            1
            for event in events
            if event.get("event_type")
            == EventType.autonomy_retry_scheduled.value
        )

        run_duration = 0.0
        if context.created_at:
            run_duration = max(
                0.0,
                (utc_now() - context.created_at).total_seconds(),
            )

        # Observation re-checks only the per-run budgets (steps, retries,
        # deadman). runs_launched / parallel_runs are launch-time gates that
        # were already enforced when this run was created; re-applying them
        # here would cause the first observation of an in-flight autonomy
        # run to always trip ``max_parallel_runs`` and falsely stop the run.
        budget_decision = agent.policy.check_budget(
            runs_launched=0,
            parallel_runs=0,
            steps_in_current_run=step_events,
            retries_for_current_step=retry_events,
            run_duration_seconds=run_duration,
        )
        if not budget_decision.allowed:
            if budget_decision.reason == "deadman_timeout_exceeded":
                return SupervisorDecision(
                    decision="stop_deadman",
                    reason=budget_decision.reason,
                    evidence=budget_decision.evidence,
                )
            return SupervisorDecision(
                decision="stop_budget_exceeded",
                reason=budget_decision.reason,
                evidence=budget_decision.evidence,
            )

        if context.state == RuntimeState.awaiting_approval:
            return SupervisorDecision(
                decision="escalate_approval",
                reason="run_awaiting_approval",
                evidence={"pending_approval_id": context.pending_approval_id},
            )

        if context.state == RuntimeState.failed:
            return SupervisorDecision(
                decision="schedule_retry",
                reason="run_failed",
                evidence={"state": context.state.value},
            )

        return SupervisorDecision(decision="continue_observe")

    def checkpoint(
        self,
        *,
        agent_id: str,
        trigger_id: str,
        run_id: Optional[str],
        status: CheckpointStatus,
        attempt: int = 1,
        last_state: Optional[str] = None,
        last_decision: Optional[str] = None,
        budget_snapshot: Optional[Dict[str, Any]] = None,
    ) -> AutonomyCheckpoint:
        checkpoint = AutonomyCheckpoint(
            agent_id=agent_id,
            trigger_id=trigger_id,
            run_id=run_id,
            status=status,
            attempt=attempt,
            last_state=last_state,
            last_decision=last_decision,
            budget_snapshot=budget_snapshot or {},
        )
        return storage.save_checkpoint(checkpoint)

    # ------------------------------------------------------------------
    # Tick
    # ------------------------------------------------------------------

    def tick(self, *, now: Optional[datetime] = None) -> Dict[str, Any]:
        if not self._enabled:
            return {"launched": 0, "observed": 0, "skipped": "disabled"}

        self._last_error = None
        launched: List[AutonomyRunLink] = []
        observed: List[str] = []
        rejected: List[str] = []
        try:
            # Observe already-running autonomy runs first so a restarted
            # supervisor never launches duplicates for the same trigger.
            for checkpoint in storage.list_active_autonomy_runs():
                if checkpoint.run_id is None:
                    continue
                observed.append(checkpoint.run_id)
                self.observe_run(checkpoint.run_id)

            triggers = self.poll_triggers(now=now)
            for trigger in triggers:
                existing = storage.load_checkpoint(
                    trigger.agent_id, trigger.trigger_id
                )
                if existing is not None and existing.run_id is not None:
                    # Already launched in a previous tick; observe only.
                    self.observe_run(existing.run_id)
                    continue

                decision = self.accept_trigger(trigger)
                if not decision.allowed:
                    rejected.append(trigger.trigger_id)
                    continue
                link = self.launch_run(trigger)
                launched.append(link)
        except Exception as exc:  # pragma: no cover - defensive
            self._last_error = f"{exc.__class__.__name__}: {exc}"
            raise
        finally:
            self._last_tick_at = utc_now()

        return {
            "launched": [link.model_dump(mode="json") for link in launched],
            "observed": observed,
            "rejected": rejected,
        }


_SUPERVISOR: Optional[AutonomySupervisor] = None
_SUPERVISOR_GUARD = threading.Lock()


def get_supervisor() -> AutonomySupervisor:
    global _SUPERVISOR
    with _SUPERVISOR_GUARD:
        if _SUPERVISOR is None:
            _SUPERVISOR = AutonomySupervisor()
        return _SUPERVISOR


def reset_supervisor() -> None:
    """Clear the module-level supervisor (test hook)."""
    global _SUPERVISOR
    with _SUPERVISOR_GUARD:
        _SUPERVISOR = None
