"""Shared pytest fixtures for backend tests.

Provides in-process FastAPI TestClient with fully isolated storage so no
Mongo instance, no sidecar, and no leftover state on disk are required.
"""

import sys
from importlib import import_module
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_ms_singleton = import_module("memory_service.singleton")
TestClient = import_module("fastapi.testclient").TestClient
create_app = import_module("backend.server").create_app


@pytest.fixture()
def isolated_memory(tmp_path, monkeypatch):
    """Give each test a fresh, empty MemoryController in a temp directory.

    Sets MEMORY_STORAGE_DIR to a unique tmp path and resets the module-level
    singleton before and after, so no state leaks between tests.
    """
    monkeypatch.delenv("MEMORY_BACKEND", raising=False)
    monkeypatch.delenv("MEMORY_SERVICE_URL", raising=False)
    monkeypatch.setenv("MEMORY_STORAGE_DIR", str(tmp_path / "memory"))
    _ms_singleton._controller = None
    yield
    _ms_singleton._controller = None


@pytest.fixture()
def app_client(tmp_path, monkeypatch, isolated_memory):
    """In-process FastAPI TestClient with isolated HCA and memory storage.

    No Mongo, no sidecar, and no shared state required. The startup handler
    catches the missing DB config and logs a warning instead of raising, so
    /status routes return 503 while all HCA and memory routes work normally.
    """
    monkeypatch.setenv("HCA_STORAGE_ROOT", str(tmp_path / "storage"))
    monkeypatch.delenv("MONGO_URL", raising=False)
    monkeypatch.delenv("DB_NAME", raising=False)
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    with TestClient(create_app()) as client:
        yield client
