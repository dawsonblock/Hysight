from fastapi.testclient import TestClient
from hca.api.app import app
import uuid

client = TestClient(app)

def test_run_and_state():
    # 1. Create run
    response = client.post("/runs", json={"goal": "echo hello"})
    assert response.status_code == 200
    run_id = response.json()["run_id"]
    
    # 2. Get state
    response = client.get(f"/runs/{run_id}/state")
    assert response.status_code == 200
    state_data = response.json()
    assert state_data["run_id"] == run_id
    assert state_data["state"] == "completed"

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
    response = client.post(f"/runs/{run_id}/approvals/{approval_id}/decide", json={"decision": "grant", "token": "test-token"})
    assert response.status_code == 200
    assert response.json()["status"] == "granted"
    
    # 4. Check state
    response = client.get(f"/runs/{run_id}/state")
    state_data = response.json()
    # If reconstruct_state fails, state_data might be different.
    # Let's print it if it fails.
    try:
        assert state_data["state"] != "awaiting_approval"
    except KeyError:
        print(f"KEY ERROR: state_data keys: {list(state_data.keys())}")
        print(f"state_data content: {state_data}")
        raise

if __name__ == "__main__":
    test_run_and_state()
    print("test_run_and_state passed")
    test_approval_via_api()
    print("test_approval_via_api passed")
