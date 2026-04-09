"""HCA API backend tests"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

class TestRootAndStatus:
    def test_root_message(self):
        r = requests.get(f"{BASE_URL}/api/")
        assert r.status_code == 200
        data = r.json()
        assert data.get("message") == "HCA API — Hybrid Cognitive Agent"

class TestHCARun:
    def test_basic_run_completed(self):
        """POST /api/hca/run - basic goal should complete"""
        r = requests.post(f"{BASE_URL}/api/hca/run", json={"goal": "Hello, what can you do?"}, timeout=60)
        assert r.status_code == 200
        data = r.json()
        print(f"state={data.get('state')}, plan={data.get('plan')}, action_result={data.get('action_result')}")
        assert data.get("state") == "completed"
        assert data.get("plan", {}).get("strategy") is not None
        assert data.get("plan", {}).get("action") is not None
        assert data.get("action_result", {}).get("status") == "success"
        TestHCARun._run_id = data.get("run_id")

    def test_get_run_by_id(self):
        """GET /api/hca/run/{run_id} returns run state"""
        run_id = getattr(TestHCARun, "_run_id", None)
        if not run_id:
            pytest.skip("No run_id from previous test")
        r = requests.get(f"{BASE_URL}/api/hca/run/{run_id}", timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert data.get("run_id") == run_id
        assert "state" in data
        assert "key_events" in data

    def test_get_run_not_found(self):
        r = requests.get(f"{BASE_URL}/api/hca/run/nonexistent-run-id", timeout=10)
        assert r.status_code == 404

class TestHCAApprovalFlow:
    def test_remember_goal_awaiting_approval(self):
        """POST /api/hca/run with 'remember' goal should return awaiting_approval"""
        r = requests.post(f"{BASE_URL}/api/hca/run", json={"goal": "Please remember that testing was done on Feb 2026"}, timeout=60)
        assert r.status_code == 200
        data = r.json()
        print(f"state={data.get('state')}, approval_id={data.get('approval_id')}")
        assert data.get("state") == "awaiting_approval"
        assert data.get("approval_id") is not None
        TestHCAApprovalFlow._run_id = data.get("run_id")
        TestHCAApprovalFlow._approval_id = data.get("approval_id")

    def test_approve_action_completes(self):
        """POST /api/hca/run/{run_id}/approve should resume and complete"""
        run_id = getattr(TestHCAApprovalFlow, "_run_id", None)
        approval_id = getattr(TestHCAApprovalFlow, "_approval_id", None)
        if not run_id or not approval_id:
            pytest.skip("No pending approval from previous test")
        r = requests.post(f"{BASE_URL}/api/hca/run/{run_id}/approve", json={"approval_id": approval_id}, timeout=60)
        assert r.status_code == 200
        data = r.json()
        print(f"After approve: state={data.get('state')}")
        assert data.get("state") == "completed"

class TestMemoryRetrieve:
    def test_memory_retrieve_returns_hits_array(self):
        """POST /api/hca/memory/retrieve with query returns hits array"""
        r = requests.post(f"{BASE_URL}/api/hca/memory/retrieve", json={"query": "hello", "top_k": 5}, timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert "hits" in data
        assert isinstance(data["hits"], list)
        print(f"Memory hits: {len(data['hits'])}")
