"""Live Mongo-backed /api/status integration proof.

This suite is opt-in and exercises the real backend persistence path against a
live MongoDB instance. Default local proof remains service-free.

    RUN_MONGO_TESTS=1 \
    MONGO_URL=mongodb://127.0.0.1:27017 \
    DB_NAME=hysight_live \
    pytest backend/tests/test_status_live_mongo.py -q
"""

from __future__ import annotations

import os
import sys
import uuid
from importlib import import_module
from pathlib import Path

import pytest
from pymongo import MongoClient

from backend.tests.contract_helpers import assert_contract_payload


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


create_app = import_module("backend.server").create_app
TestClient = import_module("fastapi.testclient").TestClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://127.0.0.1:27017")
DB_NAME = os.environ.get("DB_NAME", "hysight_live")


def _probe_mongo() -> bool:
    try:
        client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=1000)
        client.admin.command("ping")
    except Exception:
        return False
    finally:
        try:
            client.close()
        except Exception:
            pass
    return True


_USE_REAL_MONGO = (
    os.environ.get("RUN_MONGO_TESTS") == "1" and _probe_mongo()
)
_LIVE_MONGO_REASON = (
    f"requires RUN_MONGO_TESTS=1 with a live MongoDB instance at {MONGO_URL}"
)


@pytest.mark.skipif(not _USE_REAL_MONGO, reason=_LIVE_MONGO_REASON)
def test_live_status_round_trip_persists_to_mongo(monkeypatch, tmp_path):
    live_db_name = f"{DB_NAME}_{uuid.uuid4().hex[:8]}"
    storage_dir = tmp_path / "storage"
    client_name = f"live-mongo-{uuid.uuid4().hex[:8]}"

    monkeypatch.setenv("MONGO_URL", MONGO_URL)
    monkeypatch.setenv("DB_NAME", live_db_name)
    monkeypatch.setenv("MEMORY_BACKEND", "python")
    monkeypatch.delenv("MEMORY_SERVICE_URL", raising=False)
    monkeypatch.setenv("HCA_STORAGE_ROOT", str(storage_dir))
    monkeypatch.setenv("MEMORY_STORAGE_DIR", str(storage_dir / "memory"))

    mongo_client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=2000)
    mongo_client.drop_database(live_db_name)

    try:
        with TestClient(create_app()) as app_client:
            subsystems_response = app_client.get("/api/subsystems")
            assert subsystems_response.status_code == 200
            assert_contract_payload(
                "GET /api/subsystems",
                subsystems_response.json(),
            )
            assert subsystems_response.json()["database"] == {
                "enabled": True,
                "status": "healthy",
                "detail": "Mongo-backed /api/status persistence is reachable",
            }

            post_response = app_client.post(
                "/api/status",
                json={"client_name": client_name},
            )
            assert post_response.status_code == 200
            post_payload = post_response.json()
            assert_contract_payload("POST /api/status", post_payload)
            assert post_payload["client_name"] == client_name

            get_response = app_client.get("/api/status")
            assert get_response.status_code == 200
            get_payload = get_response.json()
            assert_contract_payload("GET /api/status", get_payload)
            assert len(get_payload) == 1
            assert get_payload[0]["id"] == post_payload["id"]
            assert get_payload[0]["client_name"] == client_name

        persisted_docs = list(
            mongo_client[live_db_name].status_checks.find({}, {"_id": 0})
        )
        assert len(persisted_docs) == 1
        assert persisted_docs[0]["id"] == post_payload["id"]
        assert persisted_docs[0]["client_name"] == client_name
    finally:
        mongo_client.drop_database(live_db_name)
        mongo_client.close()