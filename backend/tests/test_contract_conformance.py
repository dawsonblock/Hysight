"""Direct contract conformance checks against contract/schema.json."""

from __future__ import annotations

from importlib import import_module
from typing import Any, Dict, List

import pytest
import requests

from backend.tests.contract_helpers import assert_contract_payload


sidecar_test_module = import_module("backend.tests.test_memvid_sidecar")
FakeSidecar = sidecar_test_module._FakeSidecar
SIDECAR_URL = sidecar_test_module.SIDECAR_URL
requests_mock_lib = sidecar_test_module.rm_lib


class _FakeCursor:
    def __init__(self, docs: List[Dict[str, Any]]):
        self._docs = docs

    async def to_list(self, _limit: int):
        return list(self._docs)


class _FakeStatusChecksCollection:
    def __init__(self):
        self._docs: List[Dict[str, Any]] = []

    async def insert_one(self, doc: Dict[str, Any]):
        self._docs.append(doc)
        return object()

    def find(self, *_args, **_kwargs):
        return _FakeCursor(self._docs)


class _FakeDatabase:
    def __init__(self):
        self.status_checks = _FakeStatusChecksCollection()


@pytest.fixture()
def status_app_client(app_client, monkeypatch):
    persistence_module = import_module("backend.server_persistence")
    fake_db = _FakeDatabase()
    monkeypatch.setattr(persistence_module, "db", fake_db)
    return app_client, fake_db


@pytest.fixture()
def fake_sidecar():
    fake = FakeSidecar()
    with requests_mock_lib.Mocker() as mocker:
        mocker.post(f"{SIDECAR_URL}/memory/ingest", json=fake.ingest)
        mocker.get(f"{SIDECAR_URL}/memory/list", json=fake.list)
        mocker.post(f"{SIDECAR_URL}/memory/retrieve", json=fake.retrieve)
        mocker.post(f"{SIDECAR_URL}/memory/maintain", json=fake.maintain)
        mocker.get(f"{SIDECAR_URL}/health", json=fake.health)
        mocker.delete(
            requests_mock_lib.ANY,
            additional_matcher=lambda req: req.url.startswith(
                f"{SIDECAR_URL}/memory/"
            ),
            json=fake.delete,
        )
        yield fake


def test_backend_root_contract(app_client):
    response = app_client.get("/api/")
    assert response.status_code == 200
    assert_contract_payload("GET /api/", response.json())


def test_status_create_contract(status_app_client):
    client, _fake_db = status_app_client
    response = client.post("/api/status", json={"client_name": "contract"})
    assert response.status_code == 200
    assert_contract_payload("POST /api/status", response.json())


def test_status_list_contract(status_app_client):
    client, fake_db = status_app_client
    fake_db.status_checks._docs.append(
        {
            "id": "status-check-1",
            "client_name": "contract",
            "timestamp": "2026-01-01T00:00:00+00:00",
        }
    )
    response = client.get("/api/status")
    assert response.status_code == 200
    assert_contract_payload("GET /api/status", response.json())


def test_subsystems_contract(app_client):
    response = app_client.get("/api/subsystems")
    assert response.status_code == 200
    assert_contract_payload("GET /api/subsystems", response.json())


def test_hca_run_create_contract(app_client):
    response = app_client.post(
        "/api/hca/run",
        json={"goal": "Hello, what can you do?", "user_id": None},
    )
    assert response.status_code == 200
    assert_contract_payload("POST /api/hca/run", response.json())


def test_hca_run_detail_contract(app_client):
    run_response = app_client.post(
        "/api/hca/run",
        json={"goal": "Hello, what can you do?", "user_id": None},
    )
    assert run_response.status_code == 200
    run_id = run_response.json()["run_id"]

    response = app_client.get(f"/api/hca/run/{run_id}")
    assert response.status_code == 200
    assert_contract_payload("GET /api/hca/run/{run_id}", response.json())


def test_hca_run_detail_contract_with_pending_approval(app_client):
    response = app_client.post(
        "/api/hca/run",
        json={
            "goal": "Please remember that contract approval coverage is required",
            "user_id": None,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["state"] == "awaiting_approval"
    assert_contract_payload("POST /api/hca/run", data)

    detail_response = app_client.get(f"/api/hca/run/{data['run_id']}")
    assert detail_response.status_code == 200
    assert_contract_payload(
        "GET /api/hca/run/{run_id}",
        detail_response.json(),
    )


def test_hca_approve_contract(app_client):
    pending_response = app_client.post(
        "/api/hca/run",
        json={
            "goal": "Please remember that contract approvals should complete",
            "user_id": None,
        },
    )
    assert pending_response.status_code == 200
    pending = pending_response.json()
    approval_id = pending["approval_id"]

    response = app_client.post(
        f"/api/hca/run/{pending['run_id']}/approve",
        json={"approval_id": approval_id},
    )
    assert response.status_code == 200
    assert_contract_payload("POST /api/hca/run/{run_id}/approve", response.json())


def test_hca_deny_contract(app_client):
    pending_response = app_client.post(
        "/api/hca/run",
        json={
            "goal": "Please remember that contract approvals can be denied",
            "user_id": None,
        },
    )
    assert pending_response.status_code == 200
    pending = pending_response.json()
    approval_id = pending["approval_id"]

    response = app_client.post(
        f"/api/hca/run/{pending['run_id']}/deny",
        json={"approval_id": approval_id},
    )
    assert response.status_code == 200
    assert_contract_payload("POST /api/hca/run/{run_id}/deny", response.json())


def test_hca_runs_list_contract(app_client):
    test_hca_module = import_module("backend.tests.test_hca")

    test_hca_module._seed_run("contract-run-list", "contract list goal")
    response = app_client.get("/api/hca/runs")
    assert response.status_code == 200
    assert_contract_payload("GET /api/hca/runs", response.json())


def test_hca_run_events_contract(app_client):
    test_hca_module = import_module("backend.tests.test_hca")
    context = test_hca_module._seed_run(
        "contract-run-events",
        "contract events goal",
        completed=False,
    )

    event_type_module = import_module("hca.common.enums")
    event_log_module = import_module("hca.storage.event_log")
    event_log_module.append_event(
        context,
        event_type_module.EventType.run_completed,
        "runtime",
        {"status": "success"},
    )

    response = app_client.get("/api/hca/run/contract-run-events/events")
    assert response.status_code == 200
    assert_contract_payload(
        "GET /api/hca/run/{run_id}/events",
        response.json(),
    )


def test_hca_run_artifacts_contract(app_client):
    test_hca_module = import_module("backend.tests.test_hca")

    test_hca_module._seed_run(
        "contract-run-artifacts",
        "contract artifacts goal",
    )
    test_hca_module._seed_artifact(
        "contract-run-artifacts",
        "contract-artifact-1",
        "contract artifact content",
    )

    list_response = app_client.get(
        "/api/hca/run/contract-run-artifacts/artifacts"
    )
    assert list_response.status_code == 200
    assert_contract_payload(
        "GET /api/hca/run/{run_id}/artifacts",
        list_response.json(),
    )

    detail_response = app_client.get(
        "/api/hca/run/contract-run-artifacts/artifacts/contract-artifact-1"
    )
    assert detail_response.status_code == 200
    assert_contract_payload(
        "GET /api/hca/run/{run_id}/artifacts/{artifact_id}",
        detail_response.json(),
    )


def test_backend_memory_retrieve_contract(app_client):
    controller = import_module("memory_service.singleton").get_controller()
    candidate_cls = import_module("memory_service").CandidateMemory
    controller.ingest(
        candidate_cls(raw_text="contract retrieve target", memory_type="fact")
    )
    response = app_client.post(
        "/api/hca/memory/retrieve",
        json={
            "query_text": "contract retrieve target",
            "top_k": 5,
            "memory_layer": None,
            "scope": None,
            "run_id": None,
            "include_expired": False,
            "intent": "general",
        },
    )
    assert response.status_code == 200
    assert_contract_payload("POST /api/hca/memory/retrieve", response.json())


def test_backend_memory_list_contract(app_client):
    controller = import_module("memory_service.singleton").get_controller()
    candidate_cls = import_module("memory_service").CandidateMemory
    controller.ingest(
        candidate_cls(raw_text="contract list target", memory_type="fact")
    )
    response = app_client.get("/api/hca/memory/list")
    assert response.status_code == 200
    assert_contract_payload("GET /api/hca/memory/list", response.json())


def test_backend_memory_delete_contract(app_client):
    controller = import_module("memory_service.singleton").get_controller()
    candidate_cls = import_module("memory_service").CandidateMemory
    memory_id = controller.ingest(
        candidate_cls(raw_text="contract delete target", memory_type="fact")
    )
    response = app_client.delete(f"/api/hca/memory/{memory_id}")
    assert response.status_code == 200
    assert_contract_payload(
        "DELETE /api/hca/memory/{memory_id}",
        response.json(),
    )


def test_backend_memory_maintain_contract(app_client):
    response = app_client.post("/api/hca/memory/maintain")
    assert response.status_code == 200
    assert_contract_payload("POST /api/hca/memory/maintain", response.json())


def test_sidecar_memory_ingest_contract(fake_sidecar):
    response = requests.post(
        f"{SIDECAR_URL}/memory/ingest",
        json={
            "candidate_id": "candidate-1",
            "raw_text": "contract sidecar ingest",
            "memory_type": "fact",
            "entity": "test",
            "slot": "slot",
            "value": "value",
            "confidence": 0.9,
            "salience": 0.5,
            "scope": "shared",
            "run_id": None,
            "workflow_key": None,
            "source": {
                "source_type": "system",
                "source_id": "source-1",
                "source_label": None,
                "trust_weight": 0.9,
            },
            "tags": [],
            "metadata": {},
        },
        timeout=10,
    )
    assert response.status_code == 200
    assert_contract_payload("POST /memory/ingest", response.json())


def test_sidecar_health_contract(fake_sidecar):
    response = requests.get(f"{SIDECAR_URL}/health", timeout=10)
    assert response.status_code == 200
    assert_contract_payload("GET /health", response.json())
