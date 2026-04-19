"""Autonomy event-log integration tests.

Confirms:
- autonomy events land in the existing per-run event log
- /api/hca/run/{id}/events returns them (replay path intact)
- autonomy metadata is visible on linked run records via load_run
"""

import pytest

from hca.autonomy.supervisor import reset_supervisor
from hca.common.enums import EventType
from hca.storage.event_log import read_events
from hca.storage.runs import load_run


@pytest.fixture(autouse=True)
def _reset_supervisor():
    reset_supervisor()
    yield
    reset_supervisor()


def _create_agent(client):
    return client.post(
        "/api/hca/autonomy/agents",
        json={"name": "evt-agent", "mode": "bounded"},
    ).json()


def test_autonomy_events_land_in_existing_event_log(app_client):
    agent = _create_agent(app_client)
    app_client.post(
        "/api/hca/autonomy/inbox",
        json={"agent_id": agent["agent_id"], "goal": "g"},
    )
    tick = app_client.post("/api/hca/autonomy/tick").json()
    assert tick["enabled"] is True

    checkpoints = app_client.get("/api/hca/autonomy/checkpoints").json()
    assert checkpoints["checkpoints"], "expected at least one checkpoint"
    run_id = checkpoints["checkpoints"][0]["run_id"]

    events, _ = read_events(run_id)
    types = {e["event_type"] for e in events}
    assert EventType.autonomy_run_launched.value in types
    assert EventType.autonomy_checkpoint_written.value in types


def test_events_api_exposes_autonomy_events(app_client):
    agent = _create_agent(app_client)
    app_client.post(
        "/api/hca/autonomy/inbox",
        json={"agent_id": agent["agent_id"], "goal": "g"},
    )
    app_client.post("/api/hca/autonomy/tick")

    checkpoints = app_client.get("/api/hca/autonomy/checkpoints").json()
    run_id = checkpoints["checkpoints"][0]["run_id"]

    response = app_client.get(f"/api/hca/run/{run_id}/events?limit=50")
    assert response.status_code == 200
    body = response.json()
    event_list = body.get("events") or body.get("records") or []
    assert event_list, f"no events returned: {body}"
    types = {e["event_type"] for e in event_list}
    assert EventType.autonomy_run_launched.value in types


def test_linked_run_exposes_autonomy_metadata(app_client):
    agent = _create_agent(app_client)
    app_client.post(
        "/api/hca/autonomy/inbox",
        json={"agent_id": agent["agent_id"], "goal": "metadata-goal"},
    )
    app_client.post("/api/hca/autonomy/tick")

    checkpoints = app_client.get("/api/hca/autonomy/checkpoints").json()
    run_id = checkpoints["checkpoints"][0]["run_id"]

    context = load_run(run_id)
    assert context is not None
    assert context.autonomy_agent_id == agent["agent_id"]
    assert context.autonomy_trigger_id
    assert context.autonomy_mode == "bounded"
    assert context.goal == "metadata-goal"


def test_observe_tick_emits_autonomy_run_observed(app_client):
    agent = _create_agent(app_client)
    app_client.post(
        "/api/hca/autonomy/inbox",
        json={"agent_id": agent["agent_id"], "goal": "g"},
    )
    app_client.post("/api/hca/autonomy/tick")  # launch
    app_client.post("/api/hca/autonomy/tick")  # observe

    checkpoints = app_client.get("/api/hca/autonomy/checkpoints").json()
    run_id = checkpoints["checkpoints"][0]["run_id"]
    events, _ = read_events(run_id)
    types = {e["event_type"] for e in events}
    assert EventType.autonomy_run_observed.value in types
