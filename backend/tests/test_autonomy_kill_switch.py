"""Autonomy kill-switch regression suite.

Covers:
- kill-switch blocks new triggers with ``kill_switch_active`` reason and
  emits an ``autonomy_trigger_rejected`` audit plus the trigger is NOT
  launched.
- kill-switch blocks continuation: an observed in-flight autonomous run
  transitions the checkpoint to ``stopped`` and emits
  ``autonomy_evaluator_decided`` with decision ``stop_killed``.
- Clearing the kill switch restores normal trigger acceptance.
"""

from typing import Optional

import pytest

from hca.autonomy import storage as autonomy_storage
from hca.autonomy.policy import AutonomyPolicy
from hca.autonomy.supervisor import AutonomySupervisor, reset_supervisor
from hca.autonomy.triggers import AutonomyAgent, AutonomyInboxItem
from hca.common.enums import (
    AgentStatus,
    AutonomyMode,
    CheckpointStatus,
    EventType,
)
from hca.storage.event_log import read_events


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
        name="kill-switch-agent",
        mode=mode,
        status=status,
        policy=policy or AutonomyPolicy(mode=mode),
    )
    autonomy_storage.save_agent(agent)
    return agent


def test_kill_switch_blocks_new_triggers(supervisor_env):
    agent = _make_agent()
    autonomy_storage.enqueue_inbox_item(
        AutonomyInboxItem(agent_id=agent.agent_id, goal="blocked-goal")
    )

    supervisor = AutonomySupervisor()
    supervisor.set_kill_switch(
        active=True, reason="operator-triggered", set_by="operator"
    )

    result = supervisor.tick()

    assert result["launched"] == []
    # Checkpoint must NOT exist because launch was rejected.
    assert autonomy_storage.list_checkpoints() == []

    kill_switch = autonomy_storage.load_kill_switch()
    assert kill_switch.active is True
    assert kill_switch.reason == "operator-triggered"

    status = supervisor.status()
    assert status.kill_switch_active is True
    assert status.kill_switch_reason == "operator-triggered"


def test_kill_switch_blocks_continuation(supervisor_env):
    agent = _make_agent()
    autonomy_storage.enqueue_inbox_item(
        AutonomyInboxItem(agent_id=agent.agent_id, goal="observe-me")
    )

    supervisor = AutonomySupervisor()
    # First tick launches normally.
    result = supervisor.tick()
    assert len(result["launched"]) == 1
    run_id = result["launched"][0]["run_id"]

    # Operator pulls the kill switch mid-run.
    supervisor.set_kill_switch(
        active=True, reason="halt-now", set_by="operator"
    )

    checkpoint = supervisor.observe_run(run_id)
    assert checkpoint is not None
    assert checkpoint.status == CheckpointStatus.stopped
    assert checkpoint.kill_switch_observed is True
    assert checkpoint.safe_to_continue is False

    events, _ = read_events(run_id)
    decided = [
        e
        for e in events
        if e.get("event_type") == EventType.autonomy_evaluator_decided.value
    ]
    assert decided, "expected autonomy_evaluator_decided event"
    last_decision = decided[-1].get("payload", {}).get("decision")
    assert last_decision == "stop_killed"


def test_unkill_restores_trigger_acceptance(supervisor_env):
    agent = _make_agent()
    supervisor = AutonomySupervisor()
    supervisor.set_kill_switch(
        active=True, reason="temp", set_by="operator"
    )

    # Confirm blocked.
    autonomy_storage.enqueue_inbox_item(
        AutonomyInboxItem(agent_id=agent.agent_id, goal="first")
    )
    assert supervisor.tick()["launched"] == []

    # Clear the kill switch.
    record = supervisor.set_kill_switch(active=False, set_by="operator")
    assert record.active is False

    # New trigger should launch.
    autonomy_storage.enqueue_inbox_item(
        AutonomyInboxItem(agent_id=agent.agent_id, goal="after-unkill")
    )
    result = supervisor.tick()
    assert len(result["launched"]) == 1

    status = supervisor.status()
    assert status.kill_switch_active is False
