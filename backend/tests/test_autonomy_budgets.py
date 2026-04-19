"""Autonomy budget enforcement tests.

Covers:
- max_steps_per_run breach -> autonomy_budget_exceeded + autonomy_stopped
- max_retries_per_step breach -> autonomy_stopped
- deadman_timeout breach -> autonomy_stopped (stop_deadman decision)
"""

from datetime import timedelta

import pytest

from hca.autonomy import storage as autonomy_storage
from hca.autonomy.policy import AutonomyBudget, AutonomyPolicy
from hca.autonomy.supervisor import AutonomySupervisor, reset_supervisor
from hca.autonomy.triggers import AutonomyAgent, AutonomyInboxItem
from hca.common.enums import AutonomyMode, CheckpointStatus, EventType
from hca.common.time import utc_now
from hca.storage.event_log import append_event, read_events
from hca.storage.runs import load_run, save_run


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


def _launch(policy: AutonomyPolicy):
    agent = AutonomyAgent(
        name="budget-agent",
        mode=AutonomyMode.bounded,
        policy=policy,
    )
    autonomy_storage.save_agent(agent)
    autonomy_storage.enqueue_inbox_item(
        AutonomyInboxItem(agent_id=agent.agent_id, goal="goal")
    )
    supervisor = AutonomySupervisor()
    result = supervisor.tick()
    link = result["launched"][0]
    return supervisor, agent, link


def _event_types_for_run(run_id: str):
    events, _ = read_events(run_id)
    return [e["event_type"] for e in events]


def test_max_steps_per_run_triggers_budget_exceeded(env):
    policy = AutonomyPolicy(budget=AutonomyBudget(max_steps_per_run=1))
    supervisor, _, link = _launch(policy)
    run_id = link["run_id"]

    context = load_run(run_id)
    assert context is not None
    # Synthesize two execution_started events to exceed max_steps_per_run=1.
    for _ in range(2):
        append_event(
            context,
            EventType.execution_started,
            "runtime",
            {"marker": "synthetic"},
        )

    supervisor.observe_run(run_id)

    types = _event_types_for_run(run_id)
    assert EventType.autonomy_budget_exceeded.value in types
    assert EventType.autonomy_stopped.value in types

    checkpoint = autonomy_storage.load_checkpoint(
        link["agent_id"], link["trigger_id"]
    )
    assert checkpoint is not None
    assert checkpoint.status == CheckpointStatus.stopped

    ledger = autonomy_storage.get_budget_ledger(link["agent_id"])
    assert ledger.total_steps_observed >= 2


def test_max_retries_per_step_triggers_budget_exceeded(env):
    policy = AutonomyPolicy(budget=AutonomyBudget(max_retries_per_step=0))
    supervisor, _, link = _launch(policy)
    run_id = link["run_id"]

    context = load_run(run_id)
    assert context is not None
    # Two autonomy_retry_scheduled events exceed max_retries_per_step=0.
    for _ in range(2):
        append_event(
            context,
            EventType.autonomy_retry_scheduled,
            "autonomy",
            {"marker": "synthetic"},
        )

    supervisor.observe_run(run_id)

    types = _event_types_for_run(run_id)
    assert EventType.autonomy_budget_exceeded.value in types
    assert EventType.autonomy_stopped.value in types

    ledger = autonomy_storage.get_budget_ledger(link["agent_id"])
    assert ledger.total_retries_used >= 2


def test_deadman_timeout_triggers_stop_deadman(env):
    policy = AutonomyPolicy(budget=AutonomyBudget(deadman_timeout_seconds=1))
    supervisor, _, link = _launch(policy)
    run_id = link["run_id"]

    # Rewind the run's created_at so the supervisor sees a stale duration.
    context = load_run(run_id)
    assert context is not None
    context.created_at = utc_now() - timedelta(hours=1)
    save_run(context)

    supervisor.observe_run(run_id)

    types = _event_types_for_run(run_id)
    # Deadman emits autonomy_stopped (no autonomy_budget_exceeded on the
    # deadman branch - stop_deadman is a separate decision).
    assert EventType.autonomy_stopped.value in types

    checkpoint = autonomy_storage.load_checkpoint(
        link["agent_id"], link["trigger_id"]
    )
    assert checkpoint is not None
    assert checkpoint.status == CheckpointStatus.stopped

