"""Autonomy checkpoint / resume safety tests.

Covers:
- checkpoint persists run linkage (agent_id, trigger_id, run_id)
- restart reloads checkpoint from storage
- restart observes the existing run instead of launching a duplicate
"""

import pytest

from hca.autonomy import storage as autonomy_storage
from hca.autonomy.policy import AutonomyPolicy
from hca.autonomy.supervisor import AutonomySupervisor, reset_supervisor
from hca.autonomy.triggers import AutonomyAgent, AutonomyInboxItem
from hca.common.enums import AutonomyMode, CheckpointStatus
from hca.storage.runs import load_run


@pytest.fixture()
def env(tmp_path, monkeypatch):
    storage_root = tmp_path / "storage"
    monkeypatch.setenv("HCA_STORAGE_ROOT", str(storage_root))
    monkeypatch.setenv("MEMORY_BACKEND", "python")
    monkeypatch.setenv("MEMORY_STORAGE_DIR", str(storage_root / "memory"))
    monkeypatch.delenv("MEMORY_SERVICE_URL", raising=False)
    reset_supervisor()
    yield
    reset_supervisor()


def _seed_agent_and_inbox(goal: str = "goal"):
    agent = AutonomyAgent(
        name="resume-agent",
        mode=AutonomyMode.bounded,
        policy=AutonomyPolicy(mode=AutonomyMode.bounded),
    )
    autonomy_storage.save_agent(agent)
    autonomy_storage.enqueue_inbox_item(
        AutonomyInboxItem(agent_id=agent.agent_id, goal=goal)
    )
    return agent


def test_checkpoint_persists_run_linkage(env):
    agent = _seed_agent_and_inbox()
    supervisor = AutonomySupervisor()
    result = supervisor.tick()

    link = result["launched"][0]
    checkpoint = autonomy_storage.load_checkpoint(
        agent.agent_id, link["trigger_id"]
    )
    assert checkpoint is not None
    assert checkpoint.agent_id == agent.agent_id
    assert checkpoint.trigger_id == link["trigger_id"]
    assert checkpoint.run_id == link["run_id"]
    # Run record on disk carries the autonomy metadata.
    context = load_run(link["run_id"])
    assert context is not None
    assert context.autonomy_agent_id == agent.agent_id
    assert context.autonomy_trigger_id == link["trigger_id"]


def test_restart_reloads_checkpoint_from_storage(env):
    agent = _seed_agent_and_inbox()
    first = AutonomySupervisor()
    result = first.tick()
    run_id = result["launched"][0]["run_id"]
    trigger_id = result["launched"][0]["trigger_id"]

    # Simulate a process restart by discarding the supervisor singleton.
    reset_supervisor()

    # Fresh supervisor must see the same checkpoint on disk.
    fresh = AutonomySupervisor()
    active = autonomy_storage.list_active_autonomy_runs()
    assert any(cp.run_id == run_id for cp in active)

    # Observation must not produce a new run.
    fresh_result = fresh.tick()
    assert fresh_result["launched"] == []
    assert run_id in fresh_result["observed"]

    # Original checkpoint still refers to the original run.
    checkpoint = autonomy_storage.load_checkpoint(agent.agent_id, trigger_id)
    assert checkpoint is not None
    assert checkpoint.run_id == run_id


def test_restart_does_not_duplicate_run_for_same_trigger(env):
    agent = _seed_agent_and_inbox()
    supervisor = AutonomySupervisor()
    result = supervisor.tick()
    run_id = result["launched"][0]["run_id"]
    trigger_id = result["launched"][0]["trigger_id"]

    # Drop the supervisor and re-tick. No new inbox item has been enqueued,
    # so nothing new should launch; the existing checkpoint must be observed.
    reset_supervisor()
    supervisor = AutonomySupervisor()
    second = supervisor.tick()

    assert second["launched"] == []
    checkpoint = autonomy_storage.load_checkpoint(agent.agent_id, trigger_id)
    assert checkpoint is not None
    assert checkpoint.run_id == run_id
    assert checkpoint.status in {
        CheckpointStatus.launched,
        CheckpointStatus.observing,
        CheckpointStatus.completed,
        CheckpointStatus.failed,
    }
