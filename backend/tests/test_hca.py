"""HCA API backend tests — self-contained, no external services required."""
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ── Root / health ──────────────────────────────────────────────────────────────

def test_root_message(app_client):
    r = app_client.get("/api/")
    assert r.status_code == 200
    assert r.json().get("message") == "HCA API — Hybrid Cognitive Agent"


# ── HCA Run: not-found ─────────────────────────────────────────────────────────

def test_get_run_not_found(app_client):
    r = app_client.get("/api/hca/run/nonexistent-run-id")
    assert r.status_code == 404


# ── Memory retrieve: empty store returns empty hits ───────────────────────────

def test_memory_retrieve_returns_hits_array(app_client):
    r = app_client.post("/api/hca/memory/retrieve", json={"query": "hello", "top_k": 5})
    assert r.status_code == 200
    data = r.json()
    assert "hits" in data
    assert isinstance(data["hits"], list)


def test_memory_retrieve_hit_shape(app_client):
    """Seed one record and pin the exact shape of a retrieve hit."""
    from memory_service.singleton import get_controller
    from memory_service import CandidateMemory

    get_controller().ingest(
        CandidateMemory(raw_text="the sky is blue today", memory_type="fact")
    )
    r = app_client.post(
        "/api/hca/memory/retrieve",
        json={"query": "sky blue", "top_k": 5},
    )
    assert r.status_code == 200
    hits = r.json()["hits"]
    assert len(hits) >= 1
    hit = hits[0]
    assert isinstance(hit["text"], str)
    assert isinstance(hit["score"], float)
    assert hit["score"] > 0
    assert isinstance(hit["memory_type"], str)
    assert isinstance(hit["memory_id"], str)
    assert hit["stored_at"] is not None


def test_memory_maintain_envelope(app_client):
    """Pin the maintenance report response envelope."""
    r = app_client.post("/api/hca/memory/maintain")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data["durable_memory_count"], int)
    assert isinstance(data["expired_count"], int)
    assert isinstance(data["expired_ids"], list)
    assert isinstance(data["compaction_supported"], bool)
    assert isinstance(data["compactor_status"], str)


# ── Full HCA run (slow — runs real Runtime in-process) ────────────────────────

@pytest.mark.slow
def test_basic_run_completed(app_client):
    r = app_client.post(
        "/api/hca/run",
        json={"goal": "Hello, what can you do?"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data.get("state") == "completed"
    assert data.get("plan", {}).get("strategy") is not None
    assert data.get("plan", {}).get("action") is not None
    assert data.get("action_result", {}).get("status") == "success"


@pytest.mark.slow
def test_get_run_by_id(app_client):
    r = app_client.post(
        "/api/hca/run",
        json={"goal": "Hello, what can you do?"},
    )
    assert r.status_code == 200
    run_id = r.json().get("run_id")
    assert run_id

    r2 = app_client.get(f"/api/hca/run/{run_id}")
    assert r2.status_code == 200
    data = r2.json()
    assert data.get("run_id") == run_id
    assert "state" in data
    assert "key_events" in data


@pytest.mark.slow
def test_runtime_memory_question_returns_summary(app_client):
    r = app_client.post(
        "/api/hca/run",
        json={"goal": "What facts are stored in memory?"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data.get("run_id")
    assert "state" in data


@pytest.mark.slow
def test_runtime_memory_recall_response_not_empty(app_client):
    r = app_client.post(
        "/api/hca/run",
        json={"goal": "Test memory recall"},
    )
    assert r.status_code == 200
    assert r.json()


# ── HCA approval flow (slow) ──────────────────────────────────────────────────

@pytest.mark.slow
def test_remember_goal_awaiting_approval(app_client):
    r = app_client.post(
        "/api/hca/run",
        json={"goal": "Please remember that testing was done on Feb 2026"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data.get("state") == "awaiting_approval"
    assert data.get("approval_id") is not None


@pytest.mark.slow
def test_approve_action_completes(app_client):
    r = app_client.post(
        "/api/hca/run",
        json={"goal": "Please remember that testing was done on Feb 2026"},
    )
    assert r.status_code == 200
    data = r.json()
    run_id = data.get("run_id")
    approval_id = data.get("approval_id")
    if data.get("state") != "awaiting_approval" or not approval_id:
        pytest.skip("Run did not enter awaiting_approval state")

    r2 = app_client.post(
        f"/api/hca/run/{run_id}/approve",
        json={"approval_id": approval_id},
    )
    assert r2.status_code == 200
    assert r2.json().get("state") == "completed"


# ── Status endpoints (no DB configured → 503) ────────────────────────────────

def test_status_route_returns_503_without_db(app_client):
    """app_client deletes MONGO_URL so the status route must return 503."""
    r = app_client.post("/api/status", json={"client_name": "test"})
    assert r.status_code == 503
