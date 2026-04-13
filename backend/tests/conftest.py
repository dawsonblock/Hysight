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


_REQUIRED_TEST_DEPENDENCIES = {
    "jsonschema": "jsonschema",
    "requests_mock": "requests-mock",
}
_TEST_BOOTSTRAP_HINT = (
    "Run: python -m pip install -r backend/requirements-test.txt"
)


def pytest_sessionstart(session):
    missing = []
    for module_name, package_name in _REQUIRED_TEST_DEPENDENCIES.items():
        try:
            import_module(module_name)
        except ModuleNotFoundError:
            missing.append(package_name)

    if missing:
        joined = ", ".join(sorted(missing))
        raise pytest.UsageError(
            "Backend tests require missing dependencies: "
            f"{joined}. {_TEST_BOOTSTRAP_HINT}"
        )


@pytest.fixture()
def isolated_memory(tmp_path, monkeypatch):
    """Give each test a fresh, empty MemoryController in a temp directory.

    Sets explicit python-backed memory config under one temp storage root and
    resets the module-level singleton before and after, so no state leaks
    between tests.
    """
    storage_root = tmp_path / "storage"
    monkeypatch.setenv("MEMORY_BACKEND", "python")
    monkeypatch.delenv("MEMORY_SERVICE_URL", raising=False)
    monkeypatch.setenv("HCA_STORAGE_ROOT", str(storage_root))
    monkeypatch.setenv(
        "MEMORY_STORAGE_DIR",
        str(storage_root / "memory"),
    )
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
    storage_root = tmp_path / "storage"
    monkeypatch.setenv("MEMORY_BACKEND", "python")
    monkeypatch.setenv("HCA_STORAGE_ROOT", str(storage_root))
    monkeypatch.setenv("MEMORY_STORAGE_DIR", str(storage_root / "memory"))
    monkeypatch.delenv("MONGO_URL", raising=False)
    monkeypatch.delenv("DB_NAME", raising=False)
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    with TestClient(create_app()) as client:
        yield client
