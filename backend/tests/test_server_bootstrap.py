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
paths_module = import_module("hca.paths")
BackendConfigurationError = server_module.BackendConfigurationError
_load_settings = server_module._load_settings
create_app = server_module.create_app
FastAPI = import_module("fastapi").FastAPI
TestClient = import_module("fastapi.testclient").TestClient
StorageConfigurationError = paths_module.StorageConfigurationError
storage_root = paths_module.storage_root
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
    storage_dir = tmp_path / "storage"
    monkeypatch.setenv("MEMORY_BACKEND", "python")
    monkeypatch.delenv("MEMORY_SERVICE_URL", raising=False)
    monkeypatch.setenv("HCA_STORAGE_ROOT", str(storage_dir))
    monkeypatch.setenv("MEMORY_STORAGE_DIR", str(storage_dir / "memory"))
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


def test_load_memory_settings_derives_storage_from_hca_storage_root(
    monkeypatch,
    tmp_path,
):
    storage_dir = tmp_path / "storage"
    monkeypatch.setenv("MEMORY_BACKEND", "python")
    monkeypatch.setenv("HCA_STORAGE_ROOT", str(storage_dir))
    monkeypatch.delenv("MEMORY_STORAGE_DIR", raising=False)
    monkeypatch.delenv("MEMORY_SERVICE_URL", raising=False)

    settings = memory_config.load_memory_settings()

    assert settings.storage_dir == (storage_dir / "memory").resolve()


def test_load_memory_settings_rejects_sidecar_url_in_python_mode(
    monkeypatch,
):
    monkeypatch.setenv("MEMORY_BACKEND", "python")
    monkeypatch.setenv("MEMORY_SERVICE_URL", "http://localhost:3031")

    with pytest.raises(
        MemoryConfigurationError,
        match="must be unset unless MEMORY_BACKEND=rust",
    ):
        memory_config.load_memory_settings()


def test_load_memory_settings_rejects_memory_storage_outside_root(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("MEMORY_BACKEND", "python")
    monkeypatch.setenv("HCA_STORAGE_ROOT", str(tmp_path / "storage"))
    monkeypatch.setenv(
        "MEMORY_STORAGE_DIR",
        str(tmp_path / "other-memory"),
    )
    monkeypatch.delenv("MEMORY_SERVICE_URL", raising=False)

    with pytest.raises(
        MemoryConfigurationError,
        match="inside HCA_STORAGE_ROOT",
    ):
        memory_config.load_memory_settings()


def test_storage_root_rejects_relative_explicit_path(monkeypatch):
    monkeypatch.setenv("HCA_STORAGE_ROOT", "relative/storage")

    with pytest.raises(
        StorageConfigurationError,
        match="absolute path",
    ):
        storage_root()


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


def test_fastapi_entrypoints_are_limited_to_authorized_surfaces():
    fastapi_apps = []
    for path in ROOT.rglob("*.py"):
        relative_path = path.relative_to(ROOT).as_posix()
        content = path.read_text(encoding="utf-8")
        if re.search(r"^\s*\w+\s*=\s*FastAPI\(", content, re.MULTILINE):
            fastapi_apps.append(relative_path)

    assert sorted(fastapi_apps) == [
        "backend/server.py",
        "hca/src/hca/api/app.py",
    ]

    internal_app = (
        ROOT / "hca" / "src" / "hca" / "api" / "app.py"
    ).read_text(encoding="utf-8")
    assert "internal runtime tests" in internal_app


def test_run_view_models_delegate_to_canonical_api_models():
    api_models = import_module("hca.api.models")
    run_views = import_module("hca.api.run_views")

    shared_models = [
        "RunPlanResponse",
        "RunActionResponse",
        "RunResultResponse",
        "RunMemoryHitResponse",
        "RunKeyEventResponse",
        "RunLatencySummaryResponse",
        "RunMetricsResponse",
        "RunSummaryResponse",
        "RunListResponse",
        "RunEventResponse",
        "RunEventListResponse",
        "RunArtifactResponse",
        "RunArtifactListResponse",
        "RunArtifactDetailResponse",
    ]

    for model_name in shared_models:
        assert getattr(run_views, model_name) is getattr(
            api_models,
            model_name,
        )


def test_non_test_code_does_not_append_grants_directly():
    offenders = []
    allowed_paths = {
        "hca/src/hca/storage/approvals.py",
    }

    for path in ROOT.rglob("*.py"):
        relative_path = path.relative_to(ROOT).as_posix()
        if (
            "/tests/" in relative_path
            or relative_path.startswith("backend/tests/")
        ):
            continue
        if relative_path in allowed_paths:
            continue
        content = path.read_text(encoding="utf-8")
        if "append_grant(" in content:
            offenders.append(relative_path)

    assert offenders == []


def test_run_backend_script_sets_explicit_storage_defaults():
    script = (ROOT / "scripts" / "run_backend.sh").read_text(
        encoding="utf-8"
    )
    assert (
        'HCA_STORAGE_ROOT="${HCA_STORAGE_ROOT:-$REPO_ROOT/storage}"'
        in script
    )
    assert (
        'MEMORY_STORAGE_DIR="${MEMORY_STORAGE_DIR:-$HCA_STORAGE_ROOT/memory}"'
        in script
    )
    assert (
        "MEMORY_SERVICE_URL must be unset unless MEMORY_BACKEND=rust"
        in script
    )
    assert "MEMORY_STORAGE_DIR must be inside HCA_STORAGE_ROOT" in script


def test_base_compose_does_not_export_sidecar_url():
    compose = (ROOT / "compose.yml").read_text(encoding="utf-8")
    assert re.search(r"^\s+MEMORY_SERVICE_URL:", compose, re.MULTILINE) is None


def test_proof_runner_uses_explicit_isolated_storage_env():
    proof_runner = (ROOT / "scripts" / "run_tests.py").read_text(
        encoding="utf-8"
    )
    assert "isolated_storage" in proof_runner
    assert '"MEMORY_BACKEND": "python"' in proof_runner
    assert 'env.pop("MEMORY_SERVICE_URL", None)' in proof_runner
    assert 'tempfile.mkdtemp(prefix="hysight-proof-")' in proof_runner


def test_proof_wrapper_delegates_to_canonical_proof_runner():
    script = (ROOT / "scripts" / "proof_local.sh").read_text(
        encoding="utf-8"
    )
    assert 'exec python scripts/run_tests.py "$@"' in script


def test_non_test_python_code_keeps_process_and_network_calls_bounded():
    allowed_paths = {
        "hca/src/hca/executor/sandbox.py",
        "memory_service/config.py",
        "memory_service/controller.py",
        "scripts/run_tests.py",
    }
    forbidden_patterns = [
        re.compile(r"^\s*import\s+subprocess\b"),
        re.compile(r"^\s*from\s+subprocess\b"),
        re.compile(r"^\s*import\s+requests\b"),
        re.compile(r"^\s*from\s+requests\b"),
        re.compile(r"urllib\.request\."),
        re.compile(r"httpx\."),
        re.compile(r"os\.system\("),
        re.compile(r"os\.popen\("),
        re.compile(r"subprocess\.Popen\("),
    ]
    offenders = []

    for path in ROOT.rglob("*.py"):
        relative_path = path.relative_to(ROOT).as_posix()
        if (
            "/tests/" in relative_path
            or relative_path.startswith("backend/tests/")
        ):
            continue
        if relative_path in allowed_paths:
            continue

        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            if any(pattern.search(line) for pattern in forbidden_patterns):
                offenders.append(relative_path)
                break

    assert offenders == []
