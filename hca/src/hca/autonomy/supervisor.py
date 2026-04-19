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

from pydantic import BaseModel, Field

from hca.autonomy import storage
from hca.autonomy.attention_controller import AttentionController
from hca.autonomy.checkpoint import (
    AutonomyBudgetState,
    AutonomyCheckpoint,
    AutonomyKillSwitch,
    AutonomyRunLink,
)
from hca.autonomy.evaluator import EvaluatorReport, evaluate as evaluator_evaluate
from hca.autonomy.policy import AutonomyPolicy, PolicyDecision
from hca.autonomy.reanchor import ReanchorState, build_reanchor_summary
from hca.autonomy.style_profile import AttentionMode, get_style_profile
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
from hca.storage.runs import load_run, save_run


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
    pending_escalations: int = 0
    kill_switch_active: bool = False
    kill_switch_reason: Optional[str] = None
    kill_switch_set_at: Optional[datetime] = None
    last_tick_at: Optional[datetime] = None
    last_error: Optional[str] = None
    last_evaluator_decision: Optional[str] = None
    current_attention_mode: Optional[str] = None
    interrupt_queue_length: int = 0
    reanchor_due: bool = False
    novelty_budget_remaining: Optional[int] = None
    hyperfocus_steps_used: int = 0
    last_reanchor_summary: Optional[Dict[str, Any]] = None
    dedupe_keys_tracked: int = 0
    recent_runs: List[Dict[str, Any]] = Field(default_factory=list)
    budget_ledgers: List[Dict[str, Any]] = Field(default_factory=list)
    last_checkpoint: Optional[Dict[str, Any]] = None


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

    def _find_active_checkpoint(
        self, agent_id: str
    ) -> Optional[AutonomyCheckpoint]:
        for checkpoint in storage.list_active_autonomy_runs():
            if checkpoint.agent_id == agent_id:
                return checkpoint
        return None

    def _persist_style_context(
        self, context: RunContext, checkpoint: AutonomyCheckpoint
    ) -> None:
        context.autonomy_style_profile_id = checkpoint.style_profile_id
        context.autonomy_attention_mode = checkpoint.current_attention_mode
        context.autonomy_interrupt_queue_length = len(
            checkpoint.queued_interrupts
        )
        context.autonomy_last_reanchor_summary = checkpoint.last_reanchor_summary
        save_run(context)

    def _make_reanchor_summary(
        self,
        *,
        context: RunContext,
        checkpoint: AutonomyCheckpoint,
        reason: str,
    ) -> Dict[str, Any]:
        queued = [
            str(item.get("goal"))
            for item in checkpoint.queued_interrupts
            if isinstance(item, dict) and item.get("goal")
        ]
        blocked: List[str] = []
        if context.state == RuntimeState.awaiting_approval:
            blocked.append("awaiting approval")
        next_action = (
            f"resume {checkpoint.current_subgoal or context.goal}"
            if checkpoint.current_subgoal
            else f"continue {context.goal}"
        )
        state = ReanchorState(
            primary_goal=context.goal,
            current_subgoal=checkpoint.current_subgoal or context.goal,
            active_reason=reason,
            queued=queued,
            blocked=blocked,
            next_action=next_action,
            attention_mode=AttentionMode(checkpoint.current_attention_mode),
            continuation_justification=reason,
        )
        return build_reanchor_summary(state).model_dump(mode="json")

    def _queue_interrupt_for_active_run(
        self,
        *,
        agent: AutonomyAgent,
        checkpoint: AutonomyCheckpoint,
        trigger: AutonomyTrigger,
    ) -> str:
        if checkpoint.run_id is None:
            return "reject_branch"
        context = load_run(checkpoint.run_id)
        if context is None:
            return "reject_branch"

        style_profile = get_style_profile(agent.style_profile_id)
        controller = AttentionController()
        try:
            current_mode = AttentionMode(checkpoint.current_attention_mode)
        except ValueError:
            current_mode = style_profile.default_attention_mode

        urgency_hint = float(trigger.payload.get("urgency", 0.9) or 0.9)
        novelty_hint = float(trigger.payload.get("novelty", 0.65) or 0.65)
        decision = controller.decide(
            profile=style_profile,
            current_mode=current_mode,
            goal_score=0.8,
            novelty_score=max(0.0, min(1.0, novelty_hint)),
            urgency_score=max(0.0, min(1.0, urgency_hint)),
            return_on_focus_score=0.7,
            drift_score=0.2,
            queued_interrupts=len(checkpoint.queued_interrupts) + 1,
            active_branch_count=1 + len(checkpoint.queued_branches),
            checkpoint_safe=checkpoint.safe_to_continue,
            steps_since_reanchor=int(
                checkpoint.budget_snapshot.get("steps_in_current_run", 0) or 0
            ),
            novelty_budget_used=checkpoint.novelty_budget_used,
            high_risk_pending=context.state == RuntimeState.awaiting_approval,
            kill_switch_active=storage.load_kill_switch().active,
            primary_near_completion=context.state
            in {RuntimeState.reporting, RuntimeState.memory_commit},
            hyperfocus_steps_used=checkpoint.hyperfocus_steps_used,
        )

        if decision.decision == "reject_branch":
            append_event(
                context,
                EventType.autonomy_branch_rejected,
                "autonomy",
                {
                    "trigger_id": trigger.trigger_id,
                    "goal": trigger.goal,
                    "reason": decision.reason,
                },
            )
            return decision.decision

        updated = checkpoint.model_copy(deep=True)
        updated.style_profile_id = agent.style_profile_id
        updated.current_attention_mode = decision.next_mode.value
        updated.reanchor_due_at_step = max(
            updated.reanchor_due_at_step,
            int(updated.budget_snapshot.get("steps_in_current_run", 0) or 0)
            + style_profile.reanchor_interval_steps,
        )

        queued_payload = {
            "trigger_id": trigger.trigger_id,
            "goal": trigger.goal,
            "trigger_type": trigger.trigger_type.value,
            "urgency": urgency_hint,
            "novelty": novelty_hint,
            "queued_at": utc_now().isoformat(),
        }

        if decision.decision == "switch_to_queued_interrupt":
            if updated.current_subgoal and updated.current_subgoal != trigger.goal:
                updated.queued_branches.append(
                    {
                        "goal": updated.current_subgoal,
                        "reason": "deferred_for_interrupt",
                    }
                )
            updated.current_subgoal = trigger.goal
        else:
            updated.queued_interrupts.append(queued_payload)

        if decision.next_mode == AttentionMode.hyperfocus:
            updated.hyperfocus_steps_used += 1
        elif updated.current_attention_mode != AttentionMode.hyperfocus.value:
            updated.hyperfocus_steps_used = 0

        if novelty_hint >= 0.7:
            updated.novelty_budget_used = min(
                style_profile.novelty_exploration_budget,
                updated.novelty_budget_used + 1,
            )

        updated.last_reanchor_summary = self._make_reanchor_summary(
            context=context,
            checkpoint=updated,
            reason=decision.reason or "interrupt handled",
        )
        storage.save_checkpoint(updated)
        self._persist_style_context(context, updated)

        append_event(
            context,
            EventType.autonomy_branch_queued,
            "autonomy",
            {
                "trigger_id": trigger.trigger_id,
                "goal": trigger.goal,
                "decision": decision.decision,
                "attention_mode": updated.current_attention_mode,
                "interrupt_queue_length": len(updated.queued_interrupts),
            },
        )
        append_event(
            context,
            EventType.autonomy_attention_mode_changed,
            "autonomy",
            {
                "from": checkpoint.current_attention_mode,
                "to": updated.current_attention_mode,
                "reason": decision.reason,
            },
        )
        if decision.decision == "switch_to_queued_interrupt":
            append_event(
                context,
                EventType.autonomy_reanchor_written,
                "autonomy",
                {"summary": updated.last_reanchor_summary},
            )
        inbox_item_id = trigger.payload.get("inbox_item_id")
        if isinstance(inbox_item_id, str):
            storage.complete_inbox_item(inbox_item_id)
        return decision.decision

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def status(self) -> SupervisorStatus:
        with self._lock:
            agents = storage.list_agents()
            checkpoints = storage.list_checkpoints()
            active_checkpoint_runs = storage.list_active_autonomy_runs()
            active_agents = sum(
                1 for agent in agents if agent.status == AgentStatus.active
            )
            pending = len(storage.list_inbox_items(status=InboxStatus.pending))
            pending_escalations = sum(
                1
                for checkpoint in checkpoints
                if checkpoint.status == CheckpointStatus.awaiting_approval
            )
            kill_switch = storage.load_kill_switch()
            latest_checkpoint = checkpoints[0] if checkpoints else None
            novelty_budget_remaining: Optional[int] = None
            interrupt_queue_length = 0
            current_attention_mode: Optional[str] = None
            reanchor_due = False
            hyperfocus_steps_used = 0
            last_reanchor_summary: Optional[Dict[str, Any]] = None
            if latest_checkpoint is not None:
                current_attention_mode = latest_checkpoint.current_attention_mode
                interrupt_queue_length = len(latest_checkpoint.queued_interrupts)
                hyperfocus_steps_used = latest_checkpoint.hyperfocus_steps_used
                last_reanchor_summary = latest_checkpoint.last_reanchor_summary
                steps = int(
                    latest_checkpoint.budget_snapshot.get("steps_in_current_run", 0)
                    or 0
                )
                reanchor_due = steps >= int(
                    latest_checkpoint.reanchor_due_at_step or 0
                )
                try:
                    style_profile = get_style_profile(latest_checkpoint.style_profile_id)
                    novelty_budget_remaining = max(
                        0,
                        style_profile.novelty_exploration_budget
                        - latest_checkpoint.novelty_budget_used,
                    )
                except ValueError:
                    novelty_budget_remaining = None
            return SupervisorStatus(
                enabled=self._enabled,
                running=self._running,
                loop_running=self.loop_running,
                active_agents=active_agents,
                active_runs=len(active_checkpoint_runs),
                pending_triggers=pending,
                pending_escalations=pending_escalations,
                kill_switch_active=kill_switch.active,
                kill_switch_reason=kill_switch.reason,
                kill_switch_set_at=kill_switch.set_at,
                last_tick_at=self._last_tick_at,
                last_error=self._last_error,
                last_evaluator_decision=(
                    latest_checkpoint.last_decision
                    if latest_checkpoint is not None
                    else None
                ),
                current_attention_mode=current_attention_mode,
                interrupt_queue_length=interrupt_queue_length,
                reanchor_due=reanchor_due,
                novelty_budget_remaining=novelty_budget_remaining,
                hyperfocus_steps_used=hyperfocus_steps_used,
                last_reanchor_summary=last_reanchor_summary,
                dedupe_keys_tracked=storage.count_dedupe_records(),
                recent_runs=[
                    {
                        "agent_id": checkpoint.agent_id,
                        "trigger_id": checkpoint.trigger_id,
                        "run_id": checkpoint.run_id or "",
                    }
                    for checkpoint in active_checkpoint_runs[:5]
                    if checkpoint.run_id
                ],
                budget_ledgers=[
                    ledger.model_dump(mode="json")
                    for ledger in storage.list_budget_ledgers()[:5]
                ],
                last_checkpoint=(
                    latest_checkpoint.model_dump(mode="json")
                    if latest_checkpoint is not None
                    else None
                ),
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
            if decision.allowed:
                ledger = storage.get_budget_ledger(agent.agent_id)
                budget_decision = agent.policy.check_budget(
                    runs_launched=ledger.launched_runs_total,
                    parallel_runs=ledger.active_runs,
                )
                if not budget_decision.allowed:
                    decision = budget_decision

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

        style_profile = get_style_profile(agent.style_profile_id)
        runtime = self._get_runtime()
        context = runtime.create_autonomous_run(
            trigger.goal,
            autonomy_agent_id=agent.agent_id,
            autonomy_trigger_id=trigger.trigger_id,
            autonomy_mode=agent.mode.value,
        )
        context.autonomy_style_profile_id = style_profile.profile_id
        context.autonomy_attention_mode = style_profile.default_attention_mode.value
        context.autonomy_interrupt_queue_length = 0

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
        append_event(
            context,
            EventType.autonomy_style_loaded,
            "autonomy",
            {
                "style_profile_id": style_profile.profile_id,
                "style_profile_name": style_profile.name,
            },
        )
        append_event(
            context,
            EventType.autonomy_attention_mode_changed,
            "autonomy",
            {
                "from": None,
                "to": style_profile.default_attention_mode.value,
                "reason": "style_profile_loaded",
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
        budget_snapshot["style_novelty_budget"] = (
            style_profile.novelty_exploration_budget
        )
        budget_snapshot["style_reanchor_interval_steps"] = (
            style_profile.reanchor_interval_steps
        )

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
            style_profile_id=style_profile.profile_id,
            current_attention_mode=style_profile.default_attention_mode.value,
            current_subgoal=trigger.goal,
            reanchor_due_at_step=style_profile.reanchor_interval_steps,
            last_reanchor_summary=None,
            budget_snapshot=budget_snapshot,
        )
        checkpoint.last_reanchor_summary = self._make_reanchor_summary(
            context=context,
            checkpoint=checkpoint,
            reason="fresh run launch",
        )
        context.autonomy_last_reanchor_summary = checkpoint.last_reanchor_summary
        storage.save_checkpoint(checkpoint)
        self._persist_style_context(context, checkpoint)
        append_event(
            context,
            EventType.autonomy_checkpoint_written,
            "autonomy",
            {
                "trigger_id": trigger.trigger_id,
                "status": checkpoint.status.value,
                "attempt": checkpoint.attempt,
                "safe_to_continue": checkpoint.safe_to_continue,
                "attention_mode": checkpoint.current_attention_mode,
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
        style_profile = get_style_profile(
            agent.style_profile_id if agent is not None else existing.style_profile_id
        )
        ledger = storage.get_budget_ledger(context.autonomy_agent_id)
        kill_switch = storage.load_kill_switch()

        report = evaluator_evaluate(
            context=context,
            events=events,
            policy=policy,
            ledger=ledger,
            kill_switch=kill_switch,
            idempotency=existing.idempotency,
            checkpoint=existing,
            style_profile=style_profile,
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

        snapshot = dict(existing.budget_snapshot or {})
        observed_steps = sum(
            1
            for event in events
            if event.get("event_type") == EventType.execution_started.value
        )
        observed_retries = sum(
            1
            for event in events
            if event.get("event_type")
            == EventType.autonomy_retry_scheduled.value
        )
        previous_steps = int(snapshot.get("steps_in_current_run", 0) or 0)
        previous_retries = int(snapshot.get("retries_for_current_step", 0) or 0)
        steps_delta = max(0, observed_steps - previous_steps)
        retries_delta = max(0, observed_retries - previous_retries)

        ledger_changed = False
        if steps_delta or retries_delta:
            ledger = storage.update_budget_ledger(
                context.autonomy_agent_id,
                steps_delta=steps_delta,
                retries_delta=retries_delta,
            )
            ledger_changed = True

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
            ledger = storage.update_budget_ledger(
                context.autonomy_agent_id,
                active_runs_delta=-1,
                run_completed=True,
                budget_breach=report.decision == EvaluatorDecision.stop_budget,
            )
            ledger_changed = True

        if ledger_changed:
            append_event(
                context,
                EventType.autonomy_budget_updated,
                "autonomy",
                {
                    "launched_runs_total": ledger.launched_runs_total,
                    "active_runs": ledger.active_runs,
                    "total_steps_observed": ledger.total_steps_observed,
                    "total_retries_used": ledger.total_retries_used,
                    "steps_delta": steps_delta,
                    "retries_delta": retries_delta,
                },
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

        updated_budget_snapshot = dict(snapshot)
        updated_budget_snapshot["runs_launched"] = max(
            int(updated_budget_snapshot.get("runs_launched", 0) or 0),
            ledger.launched_runs_total,
        )
        updated_budget_snapshot["parallel_runs"] = max(0, ledger.active_runs)
        updated_budget_snapshot["steps_in_current_run"] = max(
            previous_steps, observed_steps
        )
        updated_budget_snapshot["retries_for_current_step"] = max(
            previous_retries, observed_retries
        )
        updated_budget_snapshot["style_novelty_budget"] = (
            style_profile.novelty_exploration_budget
        )
        updated_budget_snapshot["style_reanchor_interval_steps"] = (
            style_profile.reanchor_interval_steps
        )

        previous_mode = (
            existing.current_attention_mode
            or style_profile.default_attention_mode.value
        )
        next_mode = str(
            report.evidence.get("next_attention_mode") or previous_mode
        )
        current_subgoal = existing.current_subgoal or context.goal
        queued_interrupts = list(existing.queued_interrupts)
        queued_branches = list(existing.queued_branches)
        hyperfocus_steps_used = existing.hyperfocus_steps_used
        novelty_budget_used = existing.novelty_budget_used
        reanchor_due_at_step = (
            existing.reanchor_due_at_step
            or style_profile.reanchor_interval_steps
        )
        last_reanchor_summary = existing.last_reanchor_summary

        if next_mode == AttentionMode.hyperfocus.value:
            hyperfocus_steps_used += 1
        elif (
            previous_mode == AttentionMode.hyperfocus.value
            and next_mode != AttentionMode.hyperfocus.value
        ):
            hyperfocus_steps_used = 0

        if report.decision == EvaluatorDecision.reanchor:
            next_mode = AttentionMode.reanchor.value
            reanchor_due_at_step = observed_steps + style_profile.reanchor_interval_steps
        elif report.decision == EvaluatorDecision.switch_branch and queued_interrupts:
            next_interrupt = queued_interrupts.pop(0)
            prior_subgoal = current_subgoal
            current_subgoal = str(
                next_interrupt.get("goal") or prior_subgoal or context.goal
            )
            if prior_subgoal and prior_subgoal != current_subgoal:
                queued_branches.append(
                    {
                        "goal": prior_subgoal,
                        "reason": "deferred_for_interrupt",
                    }
                )
            novelty_budget_used = min(
                style_profile.novelty_exploration_budget,
                novelty_budget_used + 1,
            )
            next_mode = AttentionMode.exploratory.value
        elif report.decision == EvaluatorDecision.complete:
            queued_interrupts = []

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
            style_profile_id=existing.style_profile_id,
            current_attention_mode=next_mode,
            current_subgoal=current_subgoal,
            queued_interrupts=queued_interrupts,
            queued_branches=queued_branches,
            reanchor_due_at_step=reanchor_due_at_step,
            hyperfocus_steps_used=hyperfocus_steps_used,
            novelty_budget_used=novelty_budget_used,
            last_reanchor_summary=last_reanchor_summary,
            budget_snapshot=updated_budget_snapshot,
        )
        updated.last_reanchor_summary = self._make_reanchor_summary(
            context=context,
            checkpoint=updated,
            reason=report.reason or decision_value,
        )
        storage.save_checkpoint(updated)
        self._persist_style_context(context, updated)

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
        if previous_mode != updated.current_attention_mode:
            append_event(
                context,
                EventType.autonomy_attention_mode_changed,
                "autonomy",
                {
                    "from": previous_mode,
                    "to": updated.current_attention_mode,
                    "reason": report.reason,
                },
            )
            if updated.current_attention_mode == AttentionMode.hyperfocus.value:
                append_event(
                    context,
                    EventType.autonomy_hyperfocus_entered,
                    "autonomy",
                    {"reason": report.reason},
                )
            elif previous_mode == AttentionMode.hyperfocus.value:
                append_event(
                    context,
                    EventType.autonomy_hyperfocus_exited,
                    "autonomy",
                    {"reason": report.reason},
                )
        if report.decision == EvaluatorDecision.reanchor:
            append_event(
                context,
                EventType.autonomy_reanchor_requested,
                "autonomy",
                {"reason": report.reason, "evidence": report.evidence},
            )
            append_event(
                context,
                EventType.autonomy_reanchor_written,
                "autonomy",
                {"summary": updated.last_reanchor_summary},
            )
        elif report.decision == EvaluatorDecision.switch_branch:
            append_event(
                context,
                EventType.autonomy_reanchor_written,
                "autonomy",
                {"summary": updated.last_reanchor_summary},
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
        queued: List[str] = []
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

                agent = storage.get_agent(trigger.agent_id)
                active_checkpoint = (
                    self._find_active_checkpoint(trigger.agent_id)
                    if agent is not None
                    else None
                )
                if (
                    agent is not None
                    and active_checkpoint is not None
                    and active_checkpoint.run_id is not None
                    and active_checkpoint.trigger_id != trigger.trigger_id
                ):
                    style_result = self._queue_interrupt_for_active_run(
                        agent=agent,
                        checkpoint=active_checkpoint,
                        trigger=trigger,
                    )
                    if style_result in {
                        "queue_interrupt",
                        "switch_to_queued_interrupt",
                    }:
                        queued.append(trigger.trigger_id)
                        continue
                    if style_result == "reject_branch":
                        rejected.append(trigger.trigger_id)
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
            "queued": queued,
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
