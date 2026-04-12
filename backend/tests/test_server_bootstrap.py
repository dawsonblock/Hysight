import sys
from importlib import import_module
from pathlib import Path
import re

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

memory_config = import_module("memory_service.config")
server_module = import_module("backend.server")
BackendConfigurationError = server_module.BackendConfigurationError
_load_settings = server_module._load_settings
create_app = server_module.create_app
FastAPI = import_module("fastapi").FastAPI
TestClient = import_module("fastapi.testclient").TestClient
MemoryConfigurationError = import_module(
    "memory_service"
).MemoryConfigurationError


_ASYNCIO_DEPRECATION_FILTER = (
    "ignore:The loop argument is deprecated since Python 3.8"
    ":DeprecationWarning"
)


def test_load_settings_allows_db_disabled_when_env_unset(monkeypatch):
    monkeypatch.delenv("MONGO_URL", raising=False)
    monkeypatch.delenv("DB_NAME", raising=False)

    settings = _load_settings()
    assert settings.database_enabled is False
    assert settings.mongo_url is None
    assert settings.db_name is None


def test_load_settings_rejects_partial_backend_env(monkeypatch):
    monkeypatch.setenv("MONGO_URL", "mongodb://localhost:27017")
    monkeypatch.delenv("DB_NAME", raising=False)

    with pytest.raises(
        BackendConfigurationError,
        match="set both MONGO_URL and DB_NAME or unset both",
    ):
        _load_settings()


def test_create_app_returns_fastapi_instance():
    assert isinstance(create_app(), FastAPI)


def test_root_route_works_without_db(monkeypatch):
    """create_app() startup must not raise without Mongo env vars."""
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
    monkeypatch.delenv("MEMORY_BACKEND", raising=False)
    monkeypatch.delenv("MEMORY_SERVICE_URL", raising=False)
    monkeypatch.setenv("MEMORY_STORAGE_DIR", str(tmp_path / "memory"))
    _ms_singleton._controller = None
    try:
        with TestClient(create_app()) as client:
            r = client.post(
                "/api/hca/memory/retrieve",
                json={"query_text": "hello", "top_k": 5},
            )
        assert r.status_code == 200
        assert "hits" in r.json()
    finally:
        _ms_singleton._controller = None


@pytest.mark.filterwarnings(_ASYNCIO_DEPRECATION_FILTER)
def test_create_app_startup_fails_with_partial_mongo_config(monkeypatch):
    monkeypatch.setenv("MONGO_URL", "mongodb://localhost:27017")
    monkeypatch.delenv("DB_NAME", raising=False)

    with pytest.raises(
        BackendConfigurationError,
        match="set both MONGO_URL and DB_NAME or unset both",
    ):
        with TestClient(create_app()):
            pass


@pytest.mark.filterwarnings(_ASYNCIO_DEPRECATION_FILTER)
def test_create_app_startup_fails_with_missing_rust_sidecar_url(monkeypatch):
    monkeypatch.delenv("MONGO_URL", raising=False)
    monkeypatch.delenv("DB_NAME", raising=False)
    monkeypatch.setenv("MEMORY_BACKEND", "rust")
    monkeypatch.delenv("MEMORY_SERVICE_URL", raising=False)

    with pytest.raises(
        MemoryConfigurationError,
        match="Example: MEMORY_SERVICE_URL=http://localhost:3031",
    ):
        with TestClient(create_app()):
            pass


@pytest.mark.filterwarnings(_ASYNCIO_DEPRECATION_FILTER)
def test_create_app_startup_fails_when_sidecar_health_check_fails(monkeypatch):
    monkeypatch.delenv("MONGO_URL", raising=False)
    monkeypatch.delenv("DB_NAME", raising=False)
    monkeypatch.setenv("MEMORY_BACKEND", "rust")
    monkeypatch.setenv("MEMORY_SERVICE_URL", "http://localhost:3031")

    def _fail_probe(*args, **kwargs):
        raise MemoryConfigurationError(
            "Rust memory backend health check failed"
        )

    monkeypatch.setattr(memory_config, "probe_memory_service", _fail_probe)

    with pytest.raises(MemoryConfigurationError, match="health check failed"):
        with TestClient(create_app()):
            pass


def test_create_app_rejects_wildcard_cors(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "*")

    with pytest.raises(
        BackendConfigurationError,
        match="comma-separated allowlist",
    ):
        create_app()


def test_create_app_rejects_invalid_cors_origin(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "localhost:3000")

    with pytest.raises(
        BackendConfigurationError,
        match="http://localhost:3000",
    ):
        create_app()


def test_frontend_uses_shared_api_client_only():
    frontend_root = ROOT / "frontend" / "src"
    direct_fetch_files = []
    direct_backend_url_files = []
    compatibility_route_files = []

    for path in frontend_root.rglob("*.js"):
        relative_path = path.relative_to(ROOT).as_posix()
        content = path.read_text(encoding="utf-8")
        if relative_path != "frontend/src/lib/api.js" and "fetch(" in content:
            direct_fetch_files.append(relative_path)
        if "http://localhost:8000" in content:
            direct_backend_url_files.append(relative_path)
        if re.search(r"['\"]/?runs(?:/|['\"])", content):
            compatibility_route_files.append(relative_path)

    assert direct_fetch_files == []
    assert direct_backend_url_files == []
    assert compatibility_route_files == []


def test_launch_surfaces_do_not_start_compatibility_app():
    launch_surfaces = [
        ROOT / "scripts" / "run_backend.sh",
        ROOT / "backend" / "Dockerfile",
        ROOT / "compose.yml",
        ROOT / "compose.sidecar.yml",
        ROOT / ".github" / "workflows" / "backend-proof.yml",
    ]

    for path in launch_surfaces:
        content = path.read_text(encoding="utf-8")
        assert "hca.api.app:app" not in content

    backend_launcher = (ROOT / "scripts" / "run_backend.sh").read_text(
        encoding="utf-8"
    )
    assert "backend.server:app" in backend_launcher


def test_backend_proof_workflow_runs_documented_proof_script():
    workflow = (
        ROOT / ".github" / "workflows" / "backend-proof.yml"
    ).read_text(encoding="utf-8")
    assert "Documented Proof Surface" in workflow
    assert "python scripts/run_tests.py" in workflow
