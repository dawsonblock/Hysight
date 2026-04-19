"""Autonomy supervisor background-loop lifecycle tests.

Covers:
- ``start_loop`` starts exactly one thread; a second call returns False.
- ``status().loop_running`` reflects the live thread state.
- ``stop_loop`` joins cleanly and flips ``loop_running`` False.
- The loop actually calls ``tick()`` (observed via ``last_tick_at``).
"""

import time

import pytest

from hca.autonomy import storage as autonomy_storage
from hca.autonomy.policy import AutonomyPolicy
from hca.autonomy.supervisor import AutonomySupervisor, reset_supervisor
from hca.autonomy.triggers import AutonomyAgent, AutonomyInboxItem
from hca.common.enums import AgentStatus, AutonomyMode


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


def _make_agent() -> AutonomyAgent:
    agent = AutonomyAgent(
        name="loop-agent",
        mode=AutonomyMode.bounded,
        status=AgentStatus.active,
        policy=AutonomyPolicy(mode=AutonomyMode.bounded),
    )
    autonomy_storage.save_agent(agent)
    return agent


def test_start_loop_single_instance_guard(supervisor_env):
    supervisor = AutonomySupervisor()
    assert supervisor.loop_running is False

    started_first = supervisor.start_loop(interval_seconds=0.1)
    try:
        assert started_first is True
        assert supervisor.loop_running is True

        # Second start should be a no-op.
        started_second = supervisor.start_loop(interval_seconds=0.1)
        assert started_second is False
        assert supervisor.loop_running is True

        status = supervisor.status()
        assert status.loop_running is True
    finally:
        assert supervisor.stop_loop(timeout_seconds=2.0) is True

    assert supervisor.loop_running is False
    assert supervisor.status().loop_running is False


def test_loop_actually_ticks(supervisor_env):
    agent = _make_agent()
    autonomy_storage.enqueue_inbox_item(
        AutonomyInboxItem(agent_id=agent.agent_id, goal="ticked-by-loop")
    )

    supervisor = AutonomySupervisor()
    assert supervisor.start_loop(interval_seconds=0.05) is True
    try:
        # Wait briefly for the loop to tick at least once.
        deadline = time.time() + 2.0
        while time.time() < deadline:
            if supervisor.status().last_tick_at is not None:
                break
            time.sleep(0.05)
    finally:
        supervisor.stop_loop(timeout_seconds=2.0)

    status = supervisor.status()
    assert status.last_tick_at is not None
    # At least one run should have launched from the inbox item.
    checkpoints = autonomy_storage.list_checkpoints()
    assert len(checkpoints) >= 1


def test_stop_loop_without_start_is_noop(supervisor_env):
    supervisor = AutonomySupervisor()
    assert supervisor.stop_loop() is False
    assert supervisor.loop_running is False
