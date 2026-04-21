"""Backend routes exposing the bounded autonomy subsystem."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from backend.server_models import (
    AutonomyAgentListResponse,
    AutonomyAgentResponse,
    AutonomyBudgetLedgerListResponse,
    AutonomyBudgetLedgerResponse,
    AutonomyBudgetModel,
    AutonomyCheckpointListResponse,
    AutonomyCheckpointResponse,
    AutonomyControlResponse,
    AutonomyEscalationListResponse,
    AutonomyEscalationResponse,
    AutonomyInboxItemResponse,
    AutonomyInboxListResponse,
    AutonomyKillSwitchResponse,
    AutonomyPolicyModel,
    AutonomyRunLinkResponse,
    AutonomyRunListResponse,
    AutonomyScheduleListResponse,
    AutonomyScheduleResponse,
    AutonomyStatusResponse,
    AutonomyWorkspaceSnapshot,
    CreateAutonomyAgentRequest,
    CreateAutonomyInboxItemRequest,
    CreateAutonomyScheduleRequest,
    SetKillSwitchRequest,
)
from hca.autonomy import storage as autonomy_storage
from hca.autonomy.checkpoint import AutonomyCheckpoint
from hca.autonomy.policy import AutonomyBudget, AutonomyPolicy
from hca.autonomy.style_profile import get_style_profile
from hca.autonomy.supervisor import get_supervisor
from hca.autonomy.triggers import (
    AutonomyAgent,
    AutonomyInboxItem,
    AutonomySchedule,
)
from hca.common.enums import AgentStatus, AutonomyMode, InboxStatus


def _agent_to_response(agent: AutonomyAgent) -> AutonomyAgentResponse:
    budget = AutonomyBudgetModel(**agent.policy.budget.model_dump())
    policy = AutonomyPolicyModel(
        mode=agent.policy.mode.value,
        enabled=agent.policy.enabled,
        budget=budget,
        approval_required_action_classes=list(
            agent.policy.approval_required_action_classes
        ),
        allowed_tool_names=list(agent.policy.allowed_tool_names),
        allowed_network_domains=list(agent.policy.allowed_network_domains),
        allowed_workspace_roots=list(agent.policy.allowed_workspace_roots),
        allow_memory_writes=agent.policy.allow_memory_writes,
        allow_external_writes=agent.policy.allow_external_writes,
        auto_resume_after_approval=agent.policy.auto_resume_after_approval,
    )
    return AutonomyAgentResponse(
        agent_id=agent.agent_id,
        name=agent.name,
        description=agent.description,
        mode=agent.mode.value,
        status=agent.status.value,
        style_profile_id=agent.style_profile_id,
        policy=policy,
        created_at=agent.created_at,
        updated_at=agent.updated_at,
    )


def _schedule_to_response(
    schedule: AutonomySchedule,
) -> AutonomyScheduleResponse:
    return AutonomyScheduleResponse(
        schedule_id=schedule.schedule_id,
        agent_id=schedule.agent_id,
        interval_seconds=schedule.interval_seconds,
        goal_override=schedule.goal_override,
        payload=dict(schedule.payload),
        enabled=schedule.enabled,
        last_fired_at=schedule.last_fired_at,
        created_at=schedule.created_at,
        updated_at=schedule.updated_at,
    )


def _inbox_to_response(item: AutonomyInboxItem) -> AutonomyInboxItemResponse:
    return AutonomyInboxItemResponse(
        item_id=item.item_id,
        agent_id=item.agent_id,
        goal=item.goal,
        payload=dict(item.payload),
        status=item.status.value,
        created_at=item.created_at,
        claimed_at=item.claimed_at,
    )


def _checkpoint_to_response(c: AutonomyCheckpoint) -> AutonomyCheckpointResponse:
    budget_snapshot = dict(c.budget_snapshot)
    style_budget = max(
        0,
        int(budget_snapshot.get("style_novelty_budget", 0) or 0)
        - int(c.novelty_budget_used or 0),
    )
    steps = int(budget_snapshot.get("steps_in_current_run", 0) or 0)
    return AutonomyCheckpointResponse(
        agent_id=c.agent_id,
        trigger_id=c.trigger_id,
        run_id=c.run_id,
        status=c.status.value,
        attempt=c.attempt,
        last_event_id=c.last_event_id,
        last_state=c.last_state,
        last_decision=c.last_decision,
        resume_allowed=c.resume_allowed,
        safe_to_continue=c.safe_to_continue,
        kill_switch_observed=c.kill_switch_observed,
        dedupe_key=c.dedupe_key,
        style_profile_id=c.style_profile_id,
        current_attention_mode=c.current_attention_mode,
        current_subgoal=c.current_subgoal,
        interrupt_queue_length=len(c.queued_interrupts),
        reanchor_due=steps >= int(c.reanchor_due_at_step or 0),
        novelty_budget_remaining=style_budget,
        hyperfocus_steps_used=c.hyperfocus_steps_used,
        last_reanchor_summary=c.last_reanchor_summary,
        checkpointed_at=c.checkpointed_at,
        budget_snapshot=budget_snapshot,
    )


def _status_to_response(status) -> AutonomyStatusResponse:
    payload = status.model_dump(mode="json")
    raw_checkpoint = getattr(status, "last_checkpoint", None)
    if raw_checkpoint is not None:
        checkpoint = (
            raw_checkpoint
            if isinstance(raw_checkpoint, AutonomyCheckpoint)
            else AutonomyCheckpoint.model_validate(raw_checkpoint)
        )
        payload["last_checkpoint"] = _checkpoint_to_response(
            checkpoint
        ).model_dump(mode="json")
    return AutonomyStatusResponse(**payload)


def register_autonomy_routes(router: APIRouter) -> None:
    @router.get(
        "/hca/autonomy/status", response_model=AutonomyStatusResponse
    )
    async def autonomy_status():
        supervisor = get_supervisor()
        status = await asyncio.to_thread(supervisor.status)
        return _status_to_response(status)

    @router.post(
        "/hca/autonomy/kill", response_model=AutonomyKillSwitchResponse
    )
    async def enable_kill_switch(payload: SetKillSwitchRequest):
        supervisor = get_supervisor()
        record = await asyncio.to_thread(
            supervisor.set_kill_switch,
            active=True,
            reason=payload.reason,
            set_by=payload.set_by,
        )
        return AutonomyKillSwitchResponse(**record.model_dump(mode="json"))

    @router.post(
        "/hca/autonomy/unkill", response_model=AutonomyKillSwitchResponse
    )
    async def clear_kill_switch(payload: SetKillSwitchRequest):
        supervisor = get_supervisor()
        record = await asyncio.to_thread(
            supervisor.set_kill_switch,
            active=False,
            reason=None,
            set_by=payload.set_by,
        )
        return AutonomyKillSwitchResponse(**record.model_dump(mode="json"))

    @router.get(
        "/hca/autonomy/budgets",
        response_model=AutonomyBudgetLedgerListResponse,
    )
    async def list_autonomy_budgets():
        ledgers = await asyncio.to_thread(autonomy_storage.list_budget_ledgers)
        return AutonomyBudgetLedgerListResponse(
            ledgers=[
                AutonomyBudgetLedgerResponse(**ledger.model_dump(mode="json"))
                for ledger in ledgers
            ]
        )

    @router.get(
        "/hca/autonomy/escalations",
        response_model=AutonomyEscalationListResponse,
    )
    async def list_autonomy_escalations():
        checkpoints = await asyncio.to_thread(autonomy_storage.list_checkpoints)
        escalated = [
            cp for cp in checkpoints if cp.status.value == "awaiting_approval"
        ]
        return AutonomyEscalationListResponse(
            escalations=[
                AutonomyEscalationResponse(
                    agent_id=cp.agent_id,
                    trigger_id=cp.trigger_id,
                    run_id=cp.run_id,
                    status=cp.status.value,
                    last_state=cp.last_state,
                    last_decision=cp.last_decision,
                    checkpointed_at=cp.checkpointed_at,
                )
                for cp in escalated
            ]
        )

    @router.get(
        "/hca/autonomy/agents", response_model=AutonomyAgentListResponse
    )
    async def list_autonomy_agents():
        agents = await asyncio.to_thread(autonomy_storage.list_agents)
        return AutonomyAgentListResponse(
            agents=[_agent_to_response(a) for a in agents]
        )

    @router.post(
        "/hca/autonomy/agents", response_model=AutonomyAgentResponse
    )
    async def create_autonomy_agent(body: CreateAutonomyAgentRequest):
        try:
            mode = AutonomyMode(body.mode)
        except ValueError as exc:
            raise HTTPException(
                status_code=400, detail=f"invalid mode: {body.mode}"
            ) from exc

        try:
            style_profile = get_style_profile(body.style_profile_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail=f"invalid style profile: {body.style_profile_id}",
            ) from exc

        if body.policy is not None:
            policy = AutonomyPolicy(
                mode=mode,
                enabled=body.policy.enabled,
                budget=AutonomyBudget(**body.policy.budget.model_dump()),
                approval_required_action_classes=list(
                    body.policy.approval_required_action_classes
                ),
                allowed_tool_names=list(body.policy.allowed_tool_names),
                allowed_network_domains=list(
                    body.policy.allowed_network_domains
                ),
                allowed_workspace_roots=list(
                    body.policy.allowed_workspace_roots
                ),
                allow_memory_writes=body.policy.allow_memory_writes,
                allow_external_writes=body.policy.allow_external_writes,
                auto_resume_after_approval=(
                    body.policy.auto_resume_after_approval
                ),
            )
        else:
            policy = AutonomyPolicy(mode=mode)

        agent = AutonomyAgent(
            name=body.name,
            description=body.description,
            mode=mode,
            policy=policy,
            style_profile_id=style_profile.profile_id,
        )
        saved = await asyncio.to_thread(autonomy_storage.save_agent, agent)
        return _agent_to_response(saved)

    @router.get(
        "/hca/autonomy/agents/{agent_id}",
        response_model=AutonomyAgentResponse,
    )
    async def get_autonomy_agent(agent_id: str):
        agent = await asyncio.to_thread(
            autonomy_storage.get_agent, agent_id
        )
        if agent is None:
            raise HTTPException(status_code=404, detail="agent not found")
        return _agent_to_response(agent)

    async def _set_status(
        agent_id: str, status: AgentStatus
    ) -> AutonomyControlResponse:
        def _apply():
            supervisor = get_supervisor()
            if status == AgentStatus.paused:
                return supervisor.pause_agent(agent_id)
            if status == AgentStatus.active:
                return supervisor.resume_agent(agent_id)
            return supervisor.stop_agent(agent_id)

        try:
            agent = await asyncio.to_thread(_apply)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return AutonomyControlResponse(
            agent_id=agent.agent_id, status=agent.status.value
        )

    @router.post(
        "/hca/autonomy/agents/{agent_id}/pause",
        response_model=AutonomyControlResponse,
    )
    async def pause_autonomy_agent(agent_id: str):
        return await _set_status(agent_id, AgentStatus.paused)

    @router.post(
        "/hca/autonomy/agents/{agent_id}/resume",
        response_model=AutonomyControlResponse,
    )
    async def resume_autonomy_agent(agent_id: str):
        return await _set_status(agent_id, AgentStatus.active)

    @router.post(
        "/hca/autonomy/agents/{agent_id}/stop",
        response_model=AutonomyControlResponse,
    )
    async def stop_autonomy_agent(agent_id: str):
        return await _set_status(agent_id, AgentStatus.stopped)

    @router.get(
        "/hca/autonomy/schedules",
        response_model=AutonomyScheduleListResponse,
    )
    async def list_autonomy_schedules():
        schedules = await asyncio.to_thread(autonomy_storage.list_schedules)
        return AutonomyScheduleListResponse(
            schedules=[_schedule_to_response(s) for s in schedules]
        )

    @router.post(
        "/hca/autonomy/schedules",
        response_model=AutonomyScheduleResponse,
    )
    async def create_autonomy_schedule(body: CreateAutonomyScheduleRequest):
        agent = await asyncio.to_thread(
            autonomy_storage.get_agent, body.agent_id
        )
        if agent is None:
            raise HTTPException(status_code=404, detail="agent not found")
        if body.interval_seconds <= 0:
            raise HTTPException(
                status_code=400, detail="interval_seconds must be positive"
            )
        schedule = AutonomySchedule(
            agent_id=body.agent_id,
            interval_seconds=body.interval_seconds,
            goal_override=body.goal_override,
            payload=dict(body.payload),
            enabled=body.enabled,
        )
        saved = await asyncio.to_thread(
            autonomy_storage.save_schedule, schedule
        )
        return _schedule_to_response(saved)

    @router.post(
        "/hca/autonomy/schedules/{schedule_id}/disable",
        response_model=AutonomyScheduleResponse,
    )
    async def disable_autonomy_schedule(schedule_id: str):
        def _apply():
            schedule = autonomy_storage.get_schedule(schedule_id)
            if schedule is None:
                return None
            schedule.enabled = False
            return autonomy_storage.save_schedule(schedule)

        schedule = await asyncio.to_thread(_apply)
        if schedule is None:
            raise HTTPException(status_code=404, detail="schedule not found")
        return _schedule_to_response(schedule)

    @router.post(
        "/hca/autonomy/schedules/{schedule_id}/enable",
        response_model=AutonomyScheduleResponse,
    )
    async def enable_autonomy_schedule(schedule_id: str):
        def _apply():
            schedule = autonomy_storage.get_schedule(schedule_id)
            if schedule is None:
                return None
            schedule.enabled = True
            return autonomy_storage.save_schedule(schedule)

        schedule = await asyncio.to_thread(_apply)
        if schedule is None:
            raise HTTPException(status_code=404, detail="schedule not found")
        return _schedule_to_response(schedule)

    @router.get(
        "/hca/autonomy/inbox",
        response_model=AutonomyInboxListResponse,
    )
    async def list_autonomy_inbox(
        agent_id: Optional[str] = Query(default=None),
        status: Optional[str] = Query(default=None),
    ):
        status_filter: Optional[InboxStatus] = None
        if status is not None:
            try:
                status_filter = InboxStatus(status)
            except ValueError as exc:
                raise HTTPException(
                    status_code=400,
                    detail=f"invalid inbox status: {status}",
                ) from exc
        items = await asyncio.to_thread(
            autonomy_storage.list_inbox_items, agent_id, status_filter
        )
        return AutonomyInboxListResponse(
            items=[_inbox_to_response(i) for i in items]
        )

    @router.post(
        "/hca/autonomy/inbox",
        response_model=AutonomyInboxItemResponse,
    )
    async def create_autonomy_inbox_item(
        body: CreateAutonomyInboxItemRequest,
    ):
        agent = await asyncio.to_thread(
            autonomy_storage.get_agent, body.agent_id
        )
        if agent is None:
            raise HTTPException(status_code=404, detail="agent not found")
        item = AutonomyInboxItem(
            agent_id=body.agent_id,
            goal=body.goal,
            payload=dict(body.payload),
        )
        saved = await asyncio.to_thread(
            autonomy_storage.enqueue_inbox_item, item
        )
        return _inbox_to_response(saved)

    @router.post(
        "/hca/autonomy/inbox/{item_id}/cancel",
        response_model=AutonomyInboxItemResponse,
    )
    async def cancel_autonomy_inbox_item(item_id: str):
        item = await asyncio.to_thread(
            autonomy_storage.cancel_inbox_item, item_id
        )
        if item is None:
            raise HTTPException(
                status_code=404, detail="inbox item not found"
            )
        return _inbox_to_response(item)

    @router.get(
        "/hca/autonomy/checkpoints",
        response_model=AutonomyCheckpointListResponse,
    )
    async def list_autonomy_checkpoints_all():
        checkpoints = await asyncio.to_thread(autonomy_storage.list_checkpoints)
        return AutonomyCheckpointListResponse(
            checkpoints=[_checkpoint_to_response(c) for c in checkpoints]
        )

    @router.get(
        "/hca/autonomy/checkpoints/{agent_id}",
        response_model=AutonomyCheckpointListResponse,
    )
    async def list_autonomy_checkpoints_for_agent(agent_id: str):
        checkpoints = await asyncio.to_thread(
            autonomy_storage.list_checkpoints, agent_id
        )
        return AutonomyCheckpointListResponse(
            checkpoints=[_checkpoint_to_response(c) for c in checkpoints]
        )

    @router.get(
        "/hca/autonomy/runs",
        response_model=AutonomyRunListResponse,
    )
    async def list_autonomy_runs():
        checkpoints = await asyncio.to_thread(
            autonomy_storage.list_active_autonomy_runs
        )
        return AutonomyRunListResponse(
            runs=[
                AutonomyRunLinkResponse(
                    agent_id=c.agent_id,
                    trigger_id=c.trigger_id,
                    run_id=c.run_id or "",
                    run_status=c.status.value,
                    last_state=c.last_state,
                    last_decision=c.last_decision,
                )
                for c in checkpoints
                if c.run_id
            ]
        )

    @router.post(
        "/hca/autonomy/tick",
        response_model=AutonomyStatusResponse,
    )
    async def tick_autonomy():
        supervisor = get_supervisor()

        def _run_tick():
            supervisor.tick()
            return supervisor.status()

        status = await asyncio.to_thread(_run_tick)
        return _status_to_response(status)

    @router.get(
        "/hca/autonomy/workspace",
        response_model=AutonomyWorkspaceSnapshot,
    )
    async def autonomy_workspace_snapshot():
        supervisor = get_supervisor()

        async def _fetch_status():
            status = await asyncio.to_thread(supervisor.status)
            return _status_to_response(status)

        async def _fetch_agents():
            agents = await asyncio.to_thread(autonomy_storage.list_agents)
            return [_agent_to_response(a) for a in agents]

        async def _fetch_schedules():
            schedules = await asyncio.to_thread(autonomy_storage.list_schedules)
            return [_schedule_to_response(s) for s in schedules]

        async def _fetch_inbox():
            items = await asyncio.to_thread(
                autonomy_storage.list_inbox_items, None, None
            )
            return [_inbox_to_response(i) for i in items]

        async def _fetch_runs():
            checkpoints = await asyncio.to_thread(
                autonomy_storage.list_active_autonomy_runs
            )
            return [
                AutonomyRunLinkResponse(
                    agent_id=c.agent_id,
                    trigger_id=c.trigger_id,
                    run_id=c.run_id or "",
                    run_status=c.status.value,
                    last_state=c.last_state,
                    last_decision=c.last_decision,
                )
                for c in checkpoints
                if c.run_id
            ]

        async def _fetch_escalations():
            checkpoints = await asyncio.to_thread(autonomy_storage.list_checkpoints)
            return [
                AutonomyEscalationResponse(
                    agent_id=cp.agent_id,
                    trigger_id=cp.trigger_id,
                    run_id=cp.run_id,
                    status=cp.status.value,
                    last_state=cp.last_state,
                    last_decision=cp.last_decision,
                    checkpointed_at=cp.checkpointed_at,
                )
                for cp in checkpoints
                if cp.status.value == "awaiting_approval"
            ]

        async def _fetch_budgets():
            ledgers = await asyncio.to_thread(autonomy_storage.list_budget_ledgers)
            return [
                AutonomyBudgetLedgerResponse(**ledger.model_dump(mode="json"))
                for ledger in ledgers
            ]

        async def _fetch_checkpoints():
            checkpoints = await asyncio.to_thread(autonomy_storage.list_checkpoints)
            return [_checkpoint_to_response(c) for c in checkpoints]

        _SECTIONS = [
            ("status", _fetch_status),
            ("agents", _fetch_agents),
            ("schedules", _fetch_schedules),
            ("inbox", _fetch_inbox),
            ("runs", _fetch_runs),
            ("escalations", _fetch_escalations),
            ("budgets", _fetch_budgets),
            ("checkpoints", _fetch_checkpoints),
        ]

        results = await asyncio.gather(
            *[fn() for _, fn in _SECTIONS],
            return_exceptions=True,
        )

        section_kwargs: dict = {}
        section_errors: dict = {}
        for (name, _), result in zip(_SECTIONS, results):
            if isinstance(result, BaseException):
                section_errors[name] = str(result)
            else:
                section_kwargs[name] = result

        return AutonomyWorkspaceSnapshot(
            snapshot_at=datetime.now(timezone.utc),
            section_errors=section_errors,
            **section_kwargs,
        )
