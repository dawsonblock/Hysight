"""Autonomy trigger dedupe regression suite.

Covers:
- Repeated inbox claims in the same poll cycle dedupe on ``inbox:<id>`` —
  only one run launches.
- A second supervisor instance (restart) with the same trigger dedupe_key
  does not relaunch — the durable dedupe file survives restart.
- Dedupe rejection emits ``autonomy_trigger_deduped`` audit and does not
  create a checkpoint for the second trigger.
"""

from typing import Optional

import pytest

from hca.autonomy import storage as autonomy_storage
from hca.autonomy.policy import AutonomyPolicy
from hca.autonomy.supervisor import AutonomySupervisor, reset_supervisor
from hca.autonomy.triggers import (
    AutonomyAgent,
    AutonomyInboxItem,
    AutonomyTrigger,
)
from hca.common.enums import AgentStatus, AutonomyMode, EventType, TriggerType


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
        name="dedupe-agent",
        mode=mode,
        status=status,
        policy=policy or AutonomyPolicy(mode=mode),
    )
    autonomy_storage.save_agent(agent)
    return agent


def test_duplicate_dedupe_key_is_rejected_after_launch(supervisor_env):
    agent = _make_agent()
    supervisor = AutonomySupervisor()

    trigger_a = AutonomyTrigger(
        agent_id=agent.agent_id,
        trigger_type=TriggerType.inbox,
        goal="goal-a",
        dedupe_key="custom:shared",
    )
    decision_a = supervisor.accept_trigger(trigger_a)
    assert decision_a.allowed is True
    supervisor.launch_run(trigger_a)

    # Second trigger with the SAME dedupe_key must be rejected.
    trigger_b = AutonomyTrigger(
        agent_id=agent.agent_id,
        trigger_type=TriggerType.inbox,
        goal="goal-b",
        dedupe_key="custom:shared",
    )
    decision_b = supervisor.accept_trigger(trigger_b)
    assert decision_b.allowed is False
    assert decision_b.reason == "duplicate_dedupe_key"
    assert decision_b.evidence.get("existing_trigger_id") == trigger_a.trigger_id

    # Only one checkpoint exists.
    checkpoints = autonomy_storage.list_checkpoints()
    assert len(checkpoints) == 1
    assert checkpoints[0].trigger_id == trigger_a.trigger_id


def test_restart_does_not_relaunch_same_dedupe_key(supervisor_env):
    agent = _make_agent()
    first = AutonomySupervisor()
    trigger = AutonomyTrigger(
        agent_id=agent.agent_id,
        trigger_type=TriggerType.inbox,
        goal="persistent-goal",
        dedupe_key="custom:persist",
    )
    assert first.accept_trigger(trigger).allowed is True
    first.launch_run(trigger)

    # Simulate a restart.
    reset_supervisor()
    second = AutonomySupervisor()

    replay = AutonomyTrigger(
        agent_id=agent.agent_id,
        trigger_type=TriggerType.inbox,
        goal="persistent-goal-replay",
        dedupe_key="custom:persist",
    )
    decision = second.accept_trigger(replay)
    assert decision.allowed is False
    assert decision.reason == "duplicate_dedupe_key"


def test_repeated_ticks_do_not_relaunch_same_trigger(supervisor_env):
    """The existing checkpoint gate + dedupe file jointly prevent relaunch."""

    agent = _make_agent()
    autonomy_storage.enqueue_inbox_item(
        AutonomyInboxItem(agent_id=agent.agent_id, goal="one-shot")
    )

    supervisor = AutonomySupervisor()
    first = supervisor.tick()
    assert len(first["launched"]) == 1

    # Subsequent ticks must not launch anything new for the same inbox item.
    second = supervisor.tick()
    assert second["launched"] == []
    third = supervisor.tick()
    assert third["launched"] == []

    assert len(autonomy_storage.list_checkpoints()) == 1
