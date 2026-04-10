import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.server import BackendConfigurationError, _load_settings, create_app
from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_load_settings_requires_backend_env(monkeypatch):
    monkeypatch.delenv("MONGO_URL", raising=False)
    monkeypatch.delenv("DB_NAME", raising=False)

    with pytest.raises(BackendConfigurationError, match="MONGO_URL, DB_NAME"):
        _load_settings()


def test_create_app_returns_fastapi_instance():
    assert isinstance(create_app(), FastAPI)


def test_root_route_works_without_db(monkeypatch):
    """create_app() startup must not raise even when Mongo env vars are absent."""
    monkeypatch.delenv("MONGO_URL", raising=False)
    monkeypatch.delenv("DB_NAME", raising=False)
    with TestClient(create_app()) as client:
        r = client.get("/api/")
    assert r.status_code == 200


def test_memory_retrieve_route_works_without_db(monkeypatch, tmp_path):
    """Memory retrieve route works in-process with no Mongo configured."""
    import memory_service.singleton as _ms_singleton

    monkeypatch.delenv("MONGO_URL", raising=False)
    monkeypatch.delenv("DB_NAME", raising=False)
    monkeypatch.setenv("MEMORY_STORAGE_DIR", str(tmp_path / "memory"))
    _ms_singleton._controller = None
    try:
        with TestClient(create_app()) as client:
            r = client.post(
                "/api/hca/memory/retrieve", json={"query": "hello", "top_k": 5}
            )
        assert r.status_code == 200
        assert "hits" in r.json()
    finally:
        _ms_singleton._controller = None