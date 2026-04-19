"""Backend autonomy API route tests — exercised via FastAPI TestClient."""

import pytest

from hca.autonomy.supervisor import reset_supervisor


@pytest.fixture(autouse=True)
def _reset_supervisor():
    reset_supervisor()
    yield
    reset_supervisor()


def _create_agent(app_client, **overrides):
    body = {"name": "ops-agent", "mode": "bounded"}
    body.update(overrides)
    response = app_client.post("/api/hca/autonomy/agents", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def test_create_and_list_agent(app_client):
    agent = _create_agent(app_client, name="alpha")
    assert agent["status"] == "active"
    assert agent["mode"] == "bounded"

    listed = app_client.get("/api/hca/autonomy/agents").json()
    assert any(a["agent_id"] == agent["agent_id"] for a in listed["agents"])


def test_get_agent_by_id(app_client):
    agent = _create_agent(app_client)
    got = app_client.get(
        f"/api/hca/autonomy/agents/{agent['agent_id']}"
    ).json()
    assert got["agent_id"] == agent["agent_id"]


def test_get_missing_agent_returns_404(app_client):
    response = app_client.get("/api/hca/autonomy/agents/unknown")
    assert response.status_code == 404


def test_pause_resume_stop_agent(app_client):
    agent = _create_agent(app_client)
    agent_id = agent["agent_id"]

    paused = app_client.post(
        f"/api/hca/autonomy/agents/{agent_id}/pause"
    ).json()
    assert paused["status"] == "paused"

    resumed = app_client.post(
        f"/api/hca/autonomy/agents/{agent_id}/resume"
    ).json()
    assert resumed["status"] == "active"

    stopped = app_client.post(
        f"/api/hca/autonomy/agents/{agent_id}/stop"
    ).json()
    assert stopped["status"] == "stopped"


def test_create_schedule_requires_existing_agent(app_client):
    response = app_client.post(
        "/api/hca/autonomy/schedules",
        json={"agent_id": "missing", "interval_seconds": 60},
    )
    assert response.status_code == 404


def test_create_and_toggle_schedule(app_client):
    agent = _create_agent(app_client)
    created = app_client.post(
        "/api/hca/autonomy/schedules",
        json={
            "agent_id": agent["agent_id"],
            "interval_seconds": 30,
            "goal_override": "scheduled-goal",
        },
    ).json()
    sched_id = created["schedule_id"]
    assert created["enabled"] is True

    disabled = app_client.post(
        f"/api/hca/autonomy/schedules/{sched_id}/disable"
    ).json()
    assert disabled["enabled"] is False

    enabled = app_client.post(
        f"/api/hca/autonomy/schedules/{sched_id}/enable"
    ).json()
    assert enabled["enabled"] is True


def test_invalid_schedule_interval_rejected(app_client):
    agent = _create_agent(app_client)
    response = app_client.post(
        "/api/hca/autonomy/schedules",
        json={"agent_id": agent["agent_id"], "interval_seconds": 0},
    )
    assert response.status_code == 400


def test_create_inbox_item_and_cancel(app_client):
    agent = _create_agent(app_client)
    created = app_client.post(
        "/api/hca/autonomy/inbox",
        json={"agent_id": agent["agent_id"], "goal": "work"},
    ).json()
    item_id = created["item_id"]
    assert created["status"] == "pending"

    listed = app_client.get("/api/hca/autonomy/inbox").json()
    assert any(i["item_id"] == item_id for i in listed["items"])

    cancelled = app_client.post(
        f"/api/hca/autonomy/inbox/{item_id}/cancel"
    ).json()
    assert cancelled["status"] == "cancelled"


def test_inbox_status_filter_rejects_invalid_value(app_client):
    response = app_client.get("/api/hca/autonomy/inbox?status=bogus")
    assert response.status_code == 400


def test_status_and_checkpoints_surface(app_client):
    agent = _create_agent(app_client)
    # Enqueue work and tick so checkpoint exists.
    app_client.post(
        "/api/hca/autonomy/inbox",
        json={"agent_id": agent["agent_id"], "goal": "g1"},
    )
    tick = app_client.post("/api/hca/autonomy/tick").json()
    assert tick["enabled"] is True

    status = app_client.get("/api/hca/autonomy/status").json()
    assert "active_agents" in status

    checkpoints_all = app_client.get(
        "/api/hca/autonomy/checkpoints"
    ).json()
    assert len(checkpoints_all["checkpoints"]) >= 1

    checkpoints_for = app_client.get(
        f"/api/hca/autonomy/checkpoints/{agent['agent_id']}"
    ).json()
    assert len(checkpoints_for["checkpoints"]) >= 1

    runs = app_client.get("/api/hca/autonomy/runs").json()
    assert "runs" in runs


def test_invalid_mode_rejected(app_client):
    response = app_client.post(
        "/api/hca/autonomy/agents",
        json={"name": "x", "mode": "not-a-mode"},
    )
    assert response.status_code == 400
