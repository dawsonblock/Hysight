from fastapi.testclient import TestClient
from hca.api.app import app

client = TestClient(app)


def test_run_and_state():
    # 1. Create run
    response = client.post("/runs", json={"goal": "echo hello"})
    assert response.status_code == 200
    run_id = response.json()["run_id"]

    # 2. Get run summary from the canonical internal route.
    response = client.get(f"/runs/{run_id}")
    assert response.status_code == 200
    state_data = response.json()
    assert state_data["run_id"] == run_id
    assert state_data["state"] == "completed"


def test_runs_list_uses_shared_summary_surface():
    response = client.post("/runs", json={"goal": "list surface"})
    assert response.status_code == 200
    run_id = response.json()["run_id"]

    response = client.get("/runs?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert any(record["run_id"] == run_id for record in data["records"])
    matching = next(
        record for record in data["records"] if record["run_id"] == run_id
    )
    assert "plan" in matching
    assert "event_count" in matching
    assert "metrics" in matching


def test_approval_via_api():
    # 1. Create run that needs approval
    response = client.post("/runs", json={"goal": "remember something"})
    run_id = response.json()["run_id"]

    # 2. Get pending approvals
    response = client.get(f"/runs/{run_id}/approvals/pending")
    assert response.status_code == 200
    pending = response.json()
    assert len(pending) > 0
    approval_id = pending[0]["approval_id"]

    # 3. Grant approval
    response = client.post(
        f"/runs/{run_id}/approvals/{approval_id}/decide",
        json={"decision": "grant", "token": "test-token"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "granted"

    # 4. Check state from the canonical internal route.
    response = client.get(f"/runs/{run_id}")
    state_data = response.json()
    assert state_data["state"] != "awaiting_approval"


def test_removed_compatibility_aliases_return_not_found():
    response = client.post("/runs", json={"goal": "echo hello again"})
    assert response.status_code == 200
    run_id = response.json()["run_id"]

    assert client.get(f"/runs/{run_id}/state").status_code == 404
    assert client.get(f"/runs/{run_id}/replay").status_code == 404
    assert client.get(f"/runs/{run_id}/events").status_code == 404
    assert client.get(f"/runs/{run_id}/artifacts").status_code == 404
    assert (
        client.get(f"/runs/{run_id}/artifacts/example-artifact").status_code
        == 404
    )
    assert client.get(f"/runs/{run_id}/approvals").status_code == 404
    assert client.get(f"/runs/{run_id}/memory/episodic").status_code == 404
    assert client.get("/memory/search?run_id=x&query=test").status_code == 404
    assert client.get("/admin/health").status_code == 404


if __name__ == "__main__":
    test_run_and_state()
    print("test_run_and_state passed")
    test_approval_via_api()
    print("test_approval_via_api passed")
