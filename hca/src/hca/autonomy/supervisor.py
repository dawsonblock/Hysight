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
    AutonomyRunLink,
)
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
    EventType,
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
    active_agents: int
    active_runs: int
    pending_triggers: int
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

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        self._running = True

    def stop(self) -> None:
        self._running = False

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
            return SupervisorStatus(
                enabled=self._enabled,
                running=self._running,
                active_agents=active_agents,
                active_runs=active_runs,
                pending_triggers=pending,
                last_tick_at=self._last_tick_at,
                last_error=self._last_error,
            )

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
            },
        )

        budget_snapshot = AutonomyBudgetState(
            runs_launched=1,
            parallel_runs=1,
            run_started_at=utc_now(),
        ).model_dump(mode="json")

        checkpoint = AutonomyCheckpoint(
            agent_id=agent.agent_id,
            trigger_id=trigger.trigger_id,
            run_id=context.run_id,
            status=CheckpointStatus.launched,
            attempt=1,
            last_state=context.state.value,
            resume_allowed=True,
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
            },
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
        decision = self.decide_next_action(context, events)

        new_status = existing.status
        if decision.decision == "escalate_approval":
            new_status = CheckpointStatus.awaiting_approval
        elif decision.decision == "stop_budget_exceeded":
            new_status = CheckpointStatus.stopped
        elif decision.decision == "stop_deadman":
            new_status = CheckpointStatus.stopped
        elif decision.decision == "schedule_retry":
            new_status = CheckpointStatus.retry_scheduled
        elif context.state == RuntimeState.completed:
            new_status = CheckpointStatus.completed
        elif context.state == RuntimeState.failed:
            new_status = CheckpointStatus.failed
        else:
            new_status = CheckpointStatus.observing

        updated = AutonomyCheckpoint(
            agent_id=existing.agent_id,
            trigger_id=existing.trigger_id,
            run_id=existing.run_id,
            status=new_status,
            attempt=existing.attempt,
            last_event_id=events[-1].get("event_id") if events else existing.last_event_id,
            last_state=context.state.value,
            last_decision=decision.decision,
            resume_allowed=decision.decision != "stop_budget_exceeded",
            budget_snapshot=existing.budget_snapshot,
        )
        storage.save_checkpoint(updated)

        append_event(
            context,
            EventType.autonomy_run_observed,
            "autonomy",
            {
                "decision": decision.decision,
                "reason": decision.reason,
                "run_state": context.state.value,
            },
        )

        if decision.decision == "escalate_approval":
            append_event(
                context,
                EventType.autonomy_escalation_requested,
                "autonomy",
                {
                    "reason": decision.reason,
                    "run_state": context.state.value,
                },
            )
        elif decision.decision == "stop_budget_exceeded":
            append_event(
                context,
                EventType.autonomy_budget_exceeded,
                "autonomy",
                {"reason": decision.reason, "evidence": decision.evidence},
            )
            append_event(
                context,
                EventType.autonomy_stopped,
                "autonomy",
                {"reason": decision.reason},
            )
        elif decision.decision == "stop_deadman":
            append_event(
                context,
                EventType.autonomy_stopped,
                "autonomy",
                {"reason": decision.reason, "evidence": decision.evidence},
            )
        elif decision.decision == "schedule_retry":
            append_event(
                context,
                EventType.autonomy_retry_scheduled,
                "autonomy",
                {"reason": decision.reason, "evidence": decision.evidence},
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
