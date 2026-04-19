"""Autonomy supervisor tests — inbox and schedule triggers launch normal runs."""

from typing import Optional

import pytest

from hca.autonomy import storage as autonomy_storage
from hca.autonomy.policy import AutonomyBudget, AutonomyPolicy
from hca.autonomy.supervisor import AutonomySupervisor, reset_supervisor
from hca.autonomy.triggers import (
    AutonomyAgent,
    AutonomyInboxItem,
    AutonomySchedule,
)
from hca.common.enums import (
    AgentStatus,
    AutonomyMode,
    CheckpointStatus,
    EventType,
    InboxStatus,
)
from hca.storage.event_log import read_events
from hca.storage.runs import load_run


@pytest.fixture()
def supervisor_env(tmp_path, monkeypatch):
    storage_root = tmp_path / "storage"
    monkeypatch.setenv("HCA_STORAGE_ROOT", str(storage_root))
    monkeypatch.setenv("MEMORY_BACKEND", "python")
    monkeypatch.setenv(
        "MEMORY_STORAGE_DIR", str(storage_root / "memory")
    )
    monkeypatch.delenv("MEMORY_SERVICE_URL", raising=False)
    reset_supervisor()
    yield
    reset_supervisor()


def _make_agent(
    *,
    mode: AutonomyMode = AutonomyMode.bounded,
    status: AgentStatus = AgentStatus.active,
    policy: Optional[AutonomyPolicy] = None,
) -> AutonomyAgent:
    agent = AutonomyAgent(
        name="test-agent",
        mode=mode,
        status=status,
        policy=policy or AutonomyPolicy(mode=mode),
    )
    autonomy_storage.save_agent(agent)
    return agent


def test_inbox_trigger_launches_normal_hca_run(supervisor_env):
    agent = _make_agent()
    item = AutonomyInboxItem(agent_id=agent.agent_id, goal="inbox-goal")
    autonomy_storage.enqueue_inbox_item(item)

    supervisor = AutonomySupervisor()
    result = supervisor.tick()

    assert len(result["launched"]) == 1
    link = result["launched"][0]
    assert link["agent_id"] == agent.agent_id
    assert link["run_id"]

    context = load_run(link["run_id"])
    assert context is not None
    assert context.autonomy_agent_id == agent.agent_id
    assert context.autonomy_trigger_id == link["trigger_id"]
    assert context.autonomy_mode == agent.mode.value
    assert context.goal == "inbox-goal"


def test_schedule_trigger_launches_normal_hca_run(supervisor_env):
    agent = _make_agent()
    schedule = AutonomySchedule(
        agent_id=agent.agent_id,
        interval_seconds=1,
        goal_override="scheduled-goal",
    )
    autonomy_storage.save_schedule(schedule)

    supervisor = AutonomySupervisor()
    result = supervisor.tick()

    assert len(result["launched"]) == 1
    link = result["launched"][0]
    context = load_run(link["run_id"])
    assert context is not None
    assert context.goal == "scheduled-goal"
    updated = autonomy_storage.get_schedule(schedule.schedule_id)
    assert updated is not None
    assert updated.last_fired_at is not None


def test_paused_agent_does_not_launch(supervisor_env):
    agent = _make_agent(status=AgentStatus.paused)
    autonomy_storage.enqueue_inbox_item(
        AutonomyInboxItem(agent_id=agent.agent_id, goal="ignored")
    )
    supervisor = AutonomySupervisor()
    result = supervisor.tick()
    assert result["launched"] == []
    # Inbox item must remain pending: it was never claimed.
    pending = autonomy_storage.list_inbox_items(
        agent_id=agent.agent_id, status=InboxStatus.pending
    )
    assert len(pending) == 1


def test_stopped_agent_does_not_launch(supervisor_env):
    agent = _make_agent(status=AgentStatus.stopped)
    autonomy_storage.enqueue_inbox_item(
        AutonomyInboxItem(agent_id=agent.agent_id, goal="ignored")
    )
    supervisor = AutonomySupervisor()
    result = supervisor.tick()
    assert result["launched"] == []


def test_supervisor_records_autonomy_events_on_run(supervisor_env):
    agent = _make_agent()
    autonomy_storage.enqueue_inbox_item(
        AutonomyInboxItem(agent_id=agent.agent_id, goal="goal-1")
    )

    supervisor = AutonomySupervisor()
    result = supervisor.tick()
    run_id = result["launched"][0]["run_id"]

    events, _ = read_events(run_id)
    event_types = [e["event_type"] for e in events]
    assert EventType.autonomy_run_launched.value in event_types
    assert EventType.autonomy_checkpoint_written.value in event_types

    audit = autonomy_storage.read_autonomy_audit()
    agent_audit = [r for r in audit if r.get("agent_id") == agent.agent_id]
    audit_events = {r.get("event") for r in agent_audit}
    assert EventType.autonomy_trigger_received.value in audit_events
    assert EventType.autonomy_trigger_accepted.value in audit_events


def test_supervisor_emits_observed_event_on_second_tick(supervisor_env):
    agent = _make_agent()
    autonomy_storage.enqueue_inbox_item(
        AutonomyInboxItem(agent_id=agent.agent_id, goal="goal")
    )
    supervisor = AutonomySupervisor()
    result = supervisor.tick()
    run_id = result["launched"][0]["run_id"]

    # A second tick with no new triggers must observe the run.
    second = supervisor.tick()
    assert run_id in second["observed"]

    events, _ = read_events(run_id)
    event_types = [e["event_type"] for e in events]
    assert EventType.autonomy_run_observed.value in event_types


def test_rejected_agent_emits_audit_rejected(supervisor_env):
    # Create an agent whose policy disables autonomy.
    policy = AutonomyPolicy(enabled=False)
    agent = _make_agent(policy=policy)
    autonomy_storage.enqueue_inbox_item(
        AutonomyInboxItem(agent_id=agent.agent_id, goal="goal")
    )
    supervisor = AutonomySupervisor()
    result = supervisor.tick()
    assert result["launched"] == []
    assert len(result["rejected"]) == 1
    audit = autonomy_storage.read_autonomy_audit()
    assert any(
        r.get("event") == EventType.autonomy_trigger_rejected.value
        for r in audit
    )


def test_checkpoint_persisted_on_launch(supervisor_env):
    agent = _make_agent()
    autonomy_storage.enqueue_inbox_item(
        AutonomyInboxItem(agent_id=agent.agent_id, goal="goal")
    )
    supervisor = AutonomySupervisor()
    result = supervisor.tick()
    run_id = result["launched"][0]["run_id"]
    trigger_id = result["launched"][0]["trigger_id"]

    checkpoint = autonomy_storage.load_checkpoint(
        agent.agent_id, trigger_id
    )
    assert checkpoint is not None
    assert checkpoint.run_id == run_id
    assert checkpoint.status in {
        CheckpointStatus.launched,
        CheckpointStatus.observing,
        CheckpointStatus.completed,
    }
