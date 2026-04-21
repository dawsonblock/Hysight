import argparse
import sys
from importlib import import_module
from pathlib import Path, PurePosixPath
import json
import re

import subprocess
import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

memory_config = import_module("memory_service.config")
persistence_module = import_module("backend.server_persistence")
memory_routes_module = import_module("backend.server_memory_routes")
memory_controller_module = import_module("memory_service.controller")
server_module = import_module("backend.server")
paths_module = import_module("hca.paths")
assert_contract_payload = import_module(
    "backend.tests.contract_helpers"
).assert_contract_payload
BackendConfigurationError = persistence_module.BackendConfigurationError
load_backend_settings = persistence_module.load_backend_settings
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

_FRONTEND_COMPATIBILITY_ROUTE_PATTERNS = (
    re.compile(r"['\"`](?:/api)?/runs(?:['\"`]|/|\?)"),
    re.compile(r"['\"`]/['\"`]\s*\+\s*['\"`]runs(?:['\"`]|/|\?)"),
    re.compile(r"['\"`](?:/api)?['\"`]\s*\+\s*['\"`]/runs(?:['\"`]|/|\?)"),
)


_BLOCKED_WORKSPACE_PATH_COMPONENTS = frozenset(
    import_module("hca.executor.tool_registry").WORKSPACE_IGNORED_DIR_NAMES
)


def _is_workspace_python_path(relative_path: str) -> bool:
    normalized = relative_path.replace("\\", "/")
    parts = PurePosixPath(normalized).parts
    return not any(
        part in _BLOCKED_WORKSPACE_PATH_COMPONENTS for part in parts
    )


@pytest.mark.parametrize(
    "relative_path",
    [
        ".pkg-venv/lib/python3.13/site-packages/example/__init__.py",
        ".venv/lib/python3.12/site-packages/pkg.py",
        "__pycache__/module.py",
        ".pytest_cache/module.py",
        ".mypy_cache/module.py",
        ".ruff_cache/module.py",
        "node_modules/pkg/index.py",
        "build/generated.py",
        "dist/generated.py",
        "target/release/generated.py",
    ],
)
def test_is_workspace_python_path_rejects_transient_directories(
    relative_path,
):
    assert _is_workspace_python_path(relative_path) is False


def test_is_workspace_python_path_accepts_repo_source_files():
    assert _is_workspace_python_path("backend/server.py") is True


def test_blocked_workspace_path_components_superset_of_production():
    """Fail loudly if the production ignore list drifts from the test list.

    The production discovery blocklist lives in
    ``hca.executor.tool_registry.WORKSPACE_IGNORED_DIR_NAMES`` and is imported
    above to seed ``_BLOCKED_WORKSPACE_PATH_COMPONENTS``. This test asserts the
    invariant that the test blocklist is always a superset of production. The
    original ``.pkg-venv`` drift (commit 422155d added it to tests only) is
    now prevented by construction plus this explicit check.
    """
    production = set(
        import_module("hca.executor.tool_registry").WORKSPACE_IGNORED_DIR_NAMES
    )
    assert production, "production blocklist is empty — unexpected"
    assert production.issubset(_BLOCKED_WORKSPACE_PATH_COMPONENTS), (
        "production WORKSPACE_IGNORED_DIR_NAMES has drifted from the test "
        "blocklist: "
        f"missing from tests = {production - _BLOCKED_WORKSPACE_PATH_COMPONENTS}"
    )
    assert ".pkg-venv" in production, (
        ".pkg-venv must remain in the production blocklist so workspace "
        "discovery never leaks transient install directories into proof "
        "evidence."
    )


def _contains_frontend_compatibility_run_route(content: str) -> bool:
    return any(
        pattern.search(content)
        for pattern in _FRONTEND_COMPATIBILITY_ROUTE_PATTERNS
    )


def test_load_settings_allows_db_disabled_when_env_unset(monkeypatch):
    monkeypatch.delenv("MONGO_URL", raising=False)
    monkeypatch.delenv("DB_NAME", raising=False)

    settings = load_backend_settings()
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
        load_backend_settings()


def test_create_app_returns_fastapi_instance():
    assert isinstance(create_app(), FastAPI)


def test_root_route_works_without_db(monkeypatch):
    """create_app() startup must not raise without Mongo env vars."""
    monkeypatch.delenv("MONGO_URL", raising=False)
    monkeypatch.delenv("DB_NAME", raising=False)
    with TestClient(create_app()) as client:
        r = client.get("/api/")
    assert r.status_code == 200


def test_subsystems_route_reports_supported_python_mode_without_db(
    monkeypatch,
    tmp_path,
):
    monkeypatch.delenv("MONGO_URL", raising=False)
    monkeypatch.delenv("DB_NAME", raising=False)
    monkeypatch.delenv("EMERGENT_LLM_KEY", raising=False)
    storage_dir = tmp_path / "storage"
    monkeypatch.setenv("MEMORY_BACKEND", "python")
    monkeypatch.delenv("MEMORY_SERVICE_URL", raising=False)
    monkeypatch.setenv("HCA_STORAGE_ROOT", str(storage_dir))
    monkeypatch.setenv("MEMORY_STORAGE_DIR", str(storage_dir / "memory"))

    with TestClient(create_app()) as client:
        response = client.get("/api/subsystems")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert data["consistency_check_passed"] is True
    assert data["replay_authority"] == "local_store"
    assert data["hca_runtime_authority"] == "python_hca_runtime"
    assert data["database"] == {
        "enabled": False,
        "status": "disabled",
        "mongo_status_mode": "disabled",
        "mongo_scope": "status_only",
        "detail": (
            "Mongo-backed /api/status persistence is disabled because "
            "MONGO_URL and DB_NAME are unset. Replay-backed HCA and "
            "memory routes remain available without Mongo."
        ),
    }
    assert data["memory"] == {
        "backend": "python",
        "uses_sidecar": False,
        "status": "healthy",
        "memory_backend_mode": "local",
        "service_available": None,
        "detail": (
            "Python in-process memory controller is the active local "
            f"memory authority at {(storage_dir / 'memory').resolve()}"
        ),
        "service_url": None,
    }
    assert data["storage"]["status"] == "writable"
    assert data["storage"]["root"] == str(storage_dir.resolve())
    assert data["storage"]["memory_dir"] == str(
        (storage_dir / "memory").resolve()
    )
    assert data["llm"] == {
        "status": "missing",
        "detail": (
            "EMERGENT_LLM_KEY is missing; LLM-backed modules will fall back when possible"
        ),
    }


@pytest.mark.filterwarnings(_ASYNCIO_DEPRECATION_FILTER)
def test_subsystems_route_reports_healthy_when_configured_services_are_ready(
    monkeypatch,
    tmp_path,
):
    storage_dir = tmp_path / "storage"
    monkeypatch.setenv("MONGO_URL", "mongodb://localhost:27017")
    monkeypatch.setenv("DB_NAME", "hysight")
    monkeypatch.setenv("MEMORY_BACKEND", "python")
    monkeypatch.delenv("MEMORY_SERVICE_URL", raising=False)
    monkeypatch.setenv("HCA_STORAGE_ROOT", str(storage_dir))
    monkeypatch.setenv("MEMORY_STORAGE_DIR", str(storage_dir / "memory"))
    monkeypatch.setenv("EMERGENT_LLM_KEY", "test-key")

    class _FakeAdmin:
        async def command(self, name: str):
            assert name == "ping"
            return {"ok": 1}

    class _FakeMongoClient:
        def __init__(self):
            self.admin = _FakeAdmin()

        def close(self):
            return None

    async def _fake_initialize_database(_settings):
        setattr(persistence_module, "client", _FakeMongoClient())
        setattr(persistence_module, "db", object())

    monkeypatch.setattr(
        persistence_module,
        "initialize_database",
        _fake_initialize_database,
    )

    with TestClient(create_app()) as client:
        response = client.get("/api/subsystems")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["consistency_check_passed"] is True
    assert data["replay_authority"] == "local_store"
    assert data["hca_runtime_authority"] == "python_hca_runtime"
    assert data["database"] == {
        "enabled": True,
        "status": "healthy",
        "mongo_status_mode": "connected",
        "mongo_scope": "status_only",
        "detail": (
            "Mongo-backed /api/status persistence is reachable. Mongo "
            "does not own replay-backed HCA or memory routes."
        ),
    }
    assert data["memory"] == {
        "backend": "python",
        "uses_sidecar": False,
        "status": "healthy",
        "memory_backend_mode": "local",
        "service_available": None,
        "detail": (
            f"Python in-process memory controller is the active local memory authority at {(storage_dir / 'memory').resolve()}"
        ),
        "service_url": None,
    }
    assert data["storage"]["status"] == "writable"
    assert data["llm"] == {
        "status": "configured",
        "detail": "EMERGENT_LLM_KEY is configured",
    }


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


def test_memory_route_wrapper_does_not_duplicate_subsystems_guidance():
    exc = memory_controller_module.MemoryBackendError(
        "Rust memory sidecar is configured as the active memory authority, "
        "but the sidecar health check failed. "
        "Check /api/subsystems for operator-facing status."
    )

    detail = memory_routes_module._memory_route_unavailable_detail(exc)

    assert detail.count("/api/subsystems") == 1
    assert ".." not in detail


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
    hardcoded_api_route_files = []
    allowed_frontend_api_files = {
        "frontend/src/lib/api.js",
        "frontend/src/lib/api.test.js",
        "frontend/src/lib/autonomy-api.js",
        "frontend/src/lib/autonomy-api.test.js",
    }

    for path in frontend_root.rglob("*.js"):
        relative_path = path.relative_to(ROOT).as_posix()
        content = path.read_text(encoding="utf-8")
        if relative_path not in allowed_frontend_api_files and "fetch(" in content:
            direct_fetch_files.append(relative_path)
        if relative_path not in allowed_frontend_api_files and "http://localhost:8000" in content:
            direct_backend_url_files.append(relative_path)
        if (
            relative_path not in allowed_frontend_api_files
            and _contains_frontend_compatibility_run_route(content)
        ):
            compatibility_route_files.append(relative_path)
        if (
            relative_path not in allowed_frontend_api_files
            and re.search(r"['\"`]\/(?:api|hca)\/", content)
        ):
            hardcoded_api_route_files.append(relative_path)

    assert direct_fetch_files == []
    assert direct_backend_url_files == []
    assert compatibility_route_files == []
    assert hardcoded_api_route_files == []


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
    assert "Baseline Local Proof Surface" in workflow
    assert "Fixture Drift Check" in workflow
    assert "Backend Integration Proof" in workflow
    assert "Backend Live Mongo Proof" in workflow
    assert "Backend Live Sidecar Proof" in workflow
    assert "python scripts/check_repo_integrity.py" in workflow
    assert "make venv" in workflow
    assert "make test" in workflow
    assert "make test-pipeline" in workflow
    assert "make test-contract" in workflow
    assert "make test-backend-baseline" in workflow
    assert "make test-backend-integration" in workflow
    assert "make test-fixture-drift" in workflow
    assert "make proof-mongo-live" in workflow
    assert "make proof-sidecar" in workflow
    assert "actions/upload-artifact@v4" in workflow
    assert "artifacts/proof/baseline.json" in workflow
    assert "artifacts/proof/pipeline.json" in workflow
    assert "artifacts/proof/contract.json" in workflow
    assert "artifacts/proof/backend-baseline.json" in workflow
    assert "artifacts/proof/integration.json" in workflow
    assert "artifacts/proof/live-mongo.json" in workflow
    assert "artifacts/proof/live-sidecar.json" in workflow
    assert "artifacts/proof/history/live-mongo-*.json" in workflow
    assert "artifacts/proof/history/live-sidecar-*.json" in workflow


def test_frontend_proof_workflow_runs_documented_proof_script():
    workflow = (
        ROOT / ".github" / "workflows" / "frontend-proof.yml"
    ).read_text(encoding="utf-8")
    assert "Frontend Proof" in workflow
    assert "python scripts/check_repo_integrity.py" in workflow
    assert "make venv" in workflow
    assert "make test-bootstrap-frontend" in workflow
    assert "make proof-frontend" in workflow
    assert "frontend-proof-receipt" in workflow
    assert 'node-version: "24"' in workflow
    assert "actions/upload-artifact@v4" in workflow
    assert "artifacts/proof/frontend.json" in workflow


def test_frontend_runtime_validation_injects_yarn_user_agent(monkeypatch):
    proof_frontend = import_module("scripts.proof_frontend")
    stage_results = []
    commands = []

    def _fake_run_command(*, name, command, cwd, env=None):
        commands.append(
            {
                "name": name,
                "command": list(command),
                "cwd": cwd,
                "env": env,
            }
        )
        if list(command) == ["node", "--version"]:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout="v24.15.0\n",
                stderr="",
            )
        if list(command) == ["yarn", "--version"]:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout="1.22.22\n",
                stderr="",
            )
        if list(command) == ["node", "./scripts/verify-runtime.js"]:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout="",
                stderr="",
            )
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(proof_frontend, "_run_command", _fake_run_command)

    node_version, yarn_version = proof_frontend._validate_runtime(stage_results)

    assert node_version == "v24.15.0"
    assert yarn_version == "1.22.22"
    assert stage_results == [
        {
            "name": "runtime-verification",
            "command": "node ./scripts/verify-runtime.js",
            "returncode": 0,
            "status": "passed",
            "node_version": "v24.15.0",
            "yarn_version": "1.22.22",
            "stdout_tail": None,
            "stderr_tail": None,
        }
    ]
    runtime_command = commands[-1]
    assert runtime_command["command"] == ["node", "./scripts/verify-runtime.js"]
    assert runtime_command["cwd"] == proof_frontend.FRONTEND_ROOT
    assert runtime_command["env"]["npm_config_user_agent"].startswith(
        "yarn/1.22.22 "
    )
    assert "node/24.15.0" in runtime_command["env"]["npm_config_user_agent"]


def test_frontend_parse_jest_counts_tracks_pending_and_todo_cases(tmp_path):
    proof_frontend = import_module("scripts.proof_frontend")
    report_path = tmp_path / "frontend-jest.json"
    report_path.write_text(
        json.dumps(
            {
                "numTotalTests": 4,
                "numPassedTests": 2,
                "numPendingTests": 1,
                "numTodoTests": 1,
                "numFailedTests": 0,
                "numRuntimeErrorTestSuites": 0,
                "numTotalTestSuites": 1,
                "numPassedTestSuites": 1,
                "numFailedTestSuites": 0,
                "success": True,
                "testResults": [
                    {
                        "name": "frontend-suite",
                        "assertionResults": [
                            {"status": "passed", "fullName": "passes"},
                            {"status": "pending", "fullName": "pending case"},
                            {"status": "todo", "title": "todo case"},
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    counts, skipped_cases, metadata = proof_frontend._parse_jest_counts(
        report_path
    )

    assert counts == {
        "total_test_count": 4,
        "passed_test_count": 2,
        "skipped_test_count": 2,
        "failed_test_count": 0,
        "error_test_count": 0,
    }
    assert skipped_cases == [
        {
            "classname": "frontend-suite",
            "name": "pending case",
            "message": "pending",
        },
        {
            "classname": "frontend-suite",
            "name": "todo case",
            "message": "todo",
        },
    ]
    assert metadata == {
        "num_total_test_suites": 1,
        "num_passed_test_suites": 1,
        "num_failed_test_suites": 0,
        "num_runtime_error_test_suites": 0,
        "success": True,
    }


def test_run_tests_external_receipt_step_requires_fresh_receipt(
    monkeypatch,
    tmp_path,
):
    run_tests = import_module("scripts.run_tests")
    receipt_path = tmp_path / "frontend.json"
    receipt_path.write_text(
        json.dumps(
            {
                "outcome": "passed",
                "total_test_count": 99,
                "passed_test_count": 99,
            }
        ),
        encoding="utf-8",
    )
    step = {
        "id": "frontend",
        "name": "Frontend proof",
        "receipt_name": "frontend",
        "external_receipt": receipt_path,
        "cmd": [sys.executable, "scripts/proof_frontend.py"],
    }

    def _fake_run(command, **kwargs):
        assert command == [sys.executable, "scripts/proof_frontend.py"]
        assert kwargs["cwd"] == run_tests.REPO_ROOT
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(run_tests.subprocess, "run", _fake_run)

    result = run_tests._run_external_receipt_step(step)

    assert result["returncode"] == 0
    assert result["counts"] == {
        "total_test_count": 0,
        "passed_test_count": 0,
        "skipped_test_count": 0,
        "failed_test_count": 0,
        "error_test_count": 0,
    }
    assert result["junit_error"] == f"missing proof receipt: {receipt_path}"
    assert receipt_path.exists() is False
    assert run_tests._validate_result(step, result) == [
        f"Frontend proof: unable to parse JUnit XML: missing proof receipt: {receipt_path}"
    ]


def test_run_tests_external_receipt_step_surfaces_failed_receipt_outcome(
    monkeypatch,
    tmp_path,
):
    run_tests = import_module("scripts.run_tests")
    receipt_path = tmp_path / "frontend.json"
    step = {
        "id": "frontend",
        "name": "Frontend proof",
        "receipt_name": "frontend",
        "external_receipt": receipt_path,
        "cmd": [sys.executable, "scripts/proof_frontend.py"],
    }

    def _fake_run(command, **kwargs):
        assert command == [sys.executable, "scripts/proof_frontend.py"]
        assert kwargs["cwd"] == run_tests.REPO_ROOT
        receipt_path.write_text(
            json.dumps(
                {
                    "outcome": "failed",
                    "failure_reason": "lint failed",
                    "total_test_count": 5,
                    "passed_test_count": 4,
                    "skipped_test_count": 1,
                    "failed_test_count": 0,
                    "error_test_count": 0,
                    "skipped_cases": [
                        {
                            "classname": "frontend-suite",
                            "name": "todo case",
                            "message": "todo",
                        }
                    ],
                    "metadata": {"num_total_test_suites": 2},
                }
            ),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0, stdout="proof ok\n", stderr="")

    monkeypatch.setattr(run_tests.subprocess, "run", _fake_run)

    result = run_tests._run_external_receipt_step(step)

    assert result["returncode"] == 0
    assert result["counts"] == {
        "total_test_count": 5,
        "passed_test_count": 4,
        "skipped_test_count": 1,
        "failed_test_count": 0,
        "error_test_count": 0,
    }
    assert result["skipped_cases"] == [
        {
            "classname": "frontend-suite",
            "name": "todo case",
            "message": "todo",
        }
    ]
    assert result["proof_metadata"] == {"num_total_test_suites": 2}
    assert result["proof_outcome"] == "failed"
    assert result["proof_failure_reason"] == "lint failed"
    assert result["junit_error"] is None
    assert run_tests._validate_result(step, result) == [
        "Frontend proof: external proof receipt outcome was 'failed'"
    ]


def test_run_tests_receipt_scope_metadata_tracks_covered_steps():
    run_tests = import_module("scripts.run_tests")

    metadata = run_tests._receipt_scope_metadata(
        [run_tests.BASELINE_STEPS[0], run_tests.FRONTEND_STEP],
        [
            {"id": "pipeline", "returncode": 0, "proof_outcome": None},
            {"id": "frontend", "returncode": 0, "proof_outcome": "passed"},
        ],
    )

    assert metadata == {
        "receipt_scope": (
            "This receipt covers only the proof steps listed in "
            "covered_proof_steps."
        ),
        "covered_proof_steps": ["pipeline", "frontend"],
        "omitted_proof_steps": [
            "backend-baseline",
            "contract",
            "integration",
            "mongo-live",
            "sidecar",
            "autonomy-optional",
        ],
        "passed_proof_steps": ["pipeline", "frontend"],
        "failed_proof_steps": [],
        "includes_optional_proof_steps": True,
    }


def test_fastapi_entrypoints_are_limited_to_authorized_surfaces():
    fastapi_apps = []
    for path in ROOT.rglob("*.py"):
        relative_path = path.relative_to(ROOT).as_posix()
        if not _is_workspace_python_path(relative_path):
            continue
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


def test_internal_compatibility_app_routes_are_minimal():
    compatibility_app = import_module("hca.api.app").app
    compatibility_routes = sorted(
        (
            route.path,
            tuple(
                sorted(
                    method
                    for method in route.methods
                    if method not in {"HEAD", "OPTIONS"}
                )
            ),
        )
        for route in compatibility_app.routes
        if route.path.startswith("/runs")
        or route.path.startswith("/memory")
        or route.path.startswith("/admin")
    )

    assert compatibility_routes == [
        ("/runs", ("GET",)),
        ("/runs", ("POST",)),
        ("/runs/{run_id}", ("GET",)),
        ("/runs/{run_id}/approvals/pending", ("GET",)),
        (
            "/runs/{run_id}/approvals/{approval_id}/decide",
            ("POST",),
        ),
    ]


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
        if not _is_workspace_python_path(relative_path):
            continue
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


def test_python_code_uses_storage_helpers_instead_of_hardcoded_runs_paths():
    offenders = []
    allowed_paths = {
        "backend/tests/test_server_bootstrap.py",
        "hca/src/hca/executor/tool_registry.py",
        "hca/src/hca/paths.py",
    }
    hardcoded_patterns = [
        re.compile(r"storage/runs"),
        re.compile(r'Path\("storage"\)\s*/\s*"runs"'),
        re.compile(r'PurePosixPath\("storage/runs"\)'),
    ]

    for path in ROOT.rglob("*.py"):
        relative_path = path.relative_to(ROOT).as_posix()
        if not _is_workspace_python_path(relative_path):
            continue
        if relative_path in allowed_paths:
            continue

        content = path.read_text(encoding="utf-8")
        if any(pattern.search(content) for pattern in hardcoded_patterns):
            offenders.append(relative_path)

    assert offenders == []


def test_run_backend_script_sets_explicit_storage_defaults():
    script = (ROOT / "scripts" / "run_backend.sh").read_text(
        encoding="utf-8"
    )
    assert 'DEFAULT_PYTHON="$REPO_ROOT/.venv/bin/python"' in script
    assert "The Python runtime package lives under ./hca and is installed editable as part of repo bootstrap." in script
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
    sidecar_compose = (ROOT / "compose.sidecar.yml").read_text(
        encoding="utf-8"
    )
    assert re.search(r"^\s+MEMORY_SERVICE_URL:", compose, re.MULTILINE) is None
    assert "MEMORY_DATA_DIR: /app/data" in sidecar_compose
    assert "sidecar-data:/app/data" in sidecar_compose


def test_makefile_exposes_local_sidecar_port_override():
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "VENV_DIR ?= .venv" in makefile
    assert "LIVE_MONGO_PORT ?= 27017" in makefile
    assert "LIVE_MONGO_URL ?= mongodb://127.0.0.1:$(LIVE_MONGO_PORT)" in makefile
    assert "LIVE_MONGO_DB_NAME ?= hysight_live" in makefile
    assert "LIVE_MONGO_IMAGE ?= mongo:7" in makefile
    assert "MEMORY_SERVICE_PORT ?= 3031" in makefile
    assert (
        "MEMORY_SERVICE_URL ?= http://localhost:$(MEMORY_SERVICE_PORT)"
        in makefile
    )
    assert "dev: venv" in makefile
    assert "venv:" in makefile
    assert "test-bootstrap-frontend" in makefile
    assert "test-bootstrap-integration" in makefile
    assert "test-backend-baseline" in makefile
    assert "test-backend-integration" in makefile
    assert "proof-frontend" in makefile
    assert "proof-mongo-live" in makefile
    assert "test-mongo-live" in makefile
    assert "test-sidecar" in makefile
    assert "proof-sidecar" in makefile
    assert "test-fixture-drift" in makefile
    assert "run-memvid-sidecar" in makefile


def test_bootstrap_contract_and_repo_integrity_sentinel_pin_repo_truth():
    bootstrap = (ROOT / "BOOTSTRAP.md").read_text(encoding="utf-8")
    integrity = (ROOT / "scripts" / "check_repo_integrity.py").read_text(
        encoding="utf-8"
    )

    assert "Where the Python package lives: `./hca`" in bootstrap
    assert "How it is installed: `make venv`" in bootstrap
    assert "What command proves it: `python scripts/run_tests.py`" in bootstrap
    assert "What failure looks like:" in bootstrap

    assert '"BOOTSTRAP.md"' in integrity
    assert '"scripts/proof_frontend.py"' in integrity
    assert '"frontend/src/lib/api.fixtures.generated.json"' in integrity
    assert '"scripts/check_repo_integrity.py"' in integrity
    assert '"dev"' in integrity
    assert '"test-bootstrap-frontend"' in integrity
    assert '"proof-frontend"' in integrity
    assert '"test-fixture-drift"' in integrity
    assert '"fixture_drift"' in integrity


def test_requirements_split_keeps_mongo_support_optional():
    baseline_requirements = (
        ROOT / "backend" / "requirements-test.txt"
    ).read_text(encoding="utf-8")
    core_requirements = (
        ROOT / "backend" / "requirements-core.txt"
    ).read_text(encoding="utf-8")
    integration_requirements = (
        ROOT / "backend" / "requirements-integration.txt"
    ).read_text(encoding="utf-8")

    assert "motor" not in baseline_requirements
    assert "pymongo" not in baseline_requirements
    assert "motor" not in core_requirements
    assert "pymongo" not in core_requirements
    assert "motor==3.3.1" in integration_requirements
    assert "pymongo==4.6.3" in integration_requirements


def test_proof_runner_uses_explicit_isolated_storage_env():
    proof_runner = (ROOT / "scripts" / "run_tests.py").read_text(
        encoding="utf-8"
    )
    assert "EXPECTED_HCA_PACKAGE_DIR" in proof_runner
    assert "PACKAGE_AUTHORITY_SENTENCE" in proof_runner
    assert "BOOTSTRAP_GUIDE" in proof_runner
    assert "REPO_VENV_DIR" in proof_runner
    assert "PROOF_ARTIFACT_DIR" in proof_runner
    assert "PROOF_HISTORY_DIR" in proof_runner
    assert "FRONTEND_PROOF_RECEIPT_PATH" in proof_runner
    assert "_validate_hca_package_authority" in proof_runner
    assert "The Python runtime package lives under ./hca and is installed editable as part of repo bootstrap." in proof_runner
    assert "EXPECTED_BASELINE_STEP_COUNTS" in proof_runner
    assert "isolated_storage" in proof_runner
    assert "BASELINE_STEPS" in proof_runner
    assert "FRONTEND_STEP" in proof_runner
    assert "INTEGRATION_STEP" in proof_runner
    assert "MONGO_LIVE_STEP" in proof_runner
    assert "external_receipt" in proof_runner
    assert "--baseline-step" in proof_runner
    assert "--frontend" in proof_runner
    assert "--strict-venv" in proof_runner
    assert '"MEMORY_BACKEND": "python"' in proof_runner
    assert "DEFAULT_MEMORY_SERVICE_PORT" in proof_runner
    assert "OPTIONAL_PROOF_ENV_KEYS" in proof_runner
    assert "HYSIGHT_PROOF_ENVIRONMENT_MODE" in proof_runner
    assert "HYSIGHT_PROOF_SERVICE_CONNECTION_MODE" in proof_runner
    assert '"MEMORY_SERVICE_PORT"' in proof_runner
    assert '"RUN_MEMVID_TESTS"' in proof_runner
    assert '"MEMORY_SERVICE_URL"' in proof_runner
    assert '"RUN_MONGO_TESTS"' in proof_runner
    assert '"MONGO_URL"' in proof_runner
    assert '"DB_NAME"' in proof_runner
    assert '--run-integration' in proof_runner
    assert '--run-live' in proof_runner
    assert 'WARNING: last ' in proof_runner
    assert 'env.pop(key, None)' in proof_runner
    assert 'tempfile.mkdtemp(prefix="hysight-proof-")' in proof_runner


def test_runtime_bootstrap_does_not_inject_hca_source_path():
    bootstrap = (ROOT / "backend" / "server_bootstrap.py").read_text(
        encoding="utf-8"
    )
    pipeline_test = (ROOT / "tests" / "test_hca_pipeline.py").read_text(
        encoding="utf-8"
    )

    assert "HCA_SRC_DIR" not in bootstrap
    assert 'hca" / "src"' not in bootstrap
    assert "HCA_SRC =" not in pipeline_test
    assert 'hca" / "src"' not in pipeline_test


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
        "scripts/proof_frontend.py",
        "scripts/proof_mongo_live.py",
        "scripts/proof_receipt.py",
        "scripts/proof_sidecar.py",
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
        if not _is_workspace_python_path(relative_path):
            continue
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


def test_optional_proof_harnesses_and_receipts_are_documented_in_repo_contract():
    frontend_harness = (ROOT / "scripts" / "proof_frontend.py").read_text(
        encoding="utf-8"
    )
    mongo_harness = (ROOT / "scripts" / "proof_mongo_live.py").read_text(
        encoding="utf-8"
    )
    sidecar_harness = (ROOT / "scripts" / "proof_sidecar.py").read_text(
        encoding="utf-8"
    )
    receipt_helper = (ROOT / "scripts" / "proof_receipt.py").read_text(
        encoding="utf-8"
    )

    assert "PROOF_RECEIPT_PATH" in frontend_harness
    assert "JEST_REPORT_PATH" in frontend_harness
    assert "FIXTURE_JUNIT_PATH" in frontend_harness
    assert "write_proof_receipt(" in frontend_harness
    assert "frontend-proof-v1" in frontend_harness
    assert '"node_version"' in frontend_harness
    assert '"yarn_version"' in frontend_harness
    assert '"stages"' in frontend_harness
    assert '"skipped_cases"' in frontend_harness
    assert '"receipt_format"' in frontend_harness
    assert '"covered_proof_steps"' in frontend_harness
    assert '"omitted_proof_steps"' in frontend_harness
    assert '"covered_stage_names"' in frontend_harness
    assert '"passed_stage_names"' in frontend_harness
    assert '"failed_stage_names"' in frontend_harness
    assert "runtime-verification" in frontend_harness
    assert "fixture-drift" in frontend_harness
    assert 'name="Frontend tests"' in frontend_harness
    assert 'name="Frontend build"' in frontend_harness
    assert "--check-fixture-drift" in frontend_harness
    assert "--json" in frontend_harness
    assert "--outputFile=" in frontend_harness
    assert "make test-bootstrap-frontend" in frontend_harness
    assert "docker_disposable_local" in mongo_harness
    assert "HYSIGHT_PROOF_ENVIRONMENT_MODE" in mongo_harness
    assert "HYSIGHT_PROOF_SERVICE_CONNECTION_MODE" in mongo_harness
    assert "_wait_for_mongo_ping" in mongo_harness
    assert "accepted TCP connections but did not answer " in mongo_harness
    assert "ping at {mongo_url}" in mongo_harness
    assert '"scripts/run_tests.py", "--mongo-live"' in mongo_harness
    assert "cargo_local_sidecar" in sidecar_harness
    assert "HYSIGHT_PROOF_ENVIRONMENT_MODE" in sidecar_harness
    assert "HYSIGHT_PROOF_SERVICE_CONNECTION_MODE" in sidecar_harness
    assert "--data-dir" in sidecar_harness
    assert "TemporaryDirectory(" in sidecar_harness
    assert "MEMORY_DATA_DIR" in sidecar_harness
    assert "hysight-sidecar-proof-" in sidecar_harness
    assert 'env["MEMORY_DATA_DIR"] = str(data_dir)' in sidecar_harness
    assert 'proof_env["MEMORY_DATA_DIR"] = str(data_dir)' in sidecar_harness
    assert "data_dir_handle.cleanup()" in sidecar_harness
    assert "_port_is_available" in sidecar_harness
    assert "MEMORY_SERVICE_PORT=3032 make proof-sidecar" in sidecar_harness
    assert '"scripts/run_tests.py", "--sidecar"' in sidecar_harness
    assert "proof-sidecar.log" in sidecar_harness
    assert "DEFAULT_RECEIPT_DIR" in receipt_helper
    assert '"proof_tier"' in receipt_helper
    assert '"environment_mode"' in receipt_helper
    assert '"passed_test_count"' in receipt_helper
    assert '"skipped_test_count"' in receipt_helper
    assert '"covered_proof_steps"' in (ROOT / "scripts" / "run_tests.py").read_text(
        encoding="utf-8"
    )
    assert '"service_endpoint"' in receipt_helper


def test_runtime_state_paths_remain_gitignored():
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "storage/" in gitignore
    assert "data/" in gitignore


def test_sidecar_proof_main_uses_isolated_temp_data_dir(
    monkeypatch,
    tmp_path,
):
    proof_sidecar = import_module("scripts.proof_sidecar")
    log_path = tmp_path / "proof-sidecar.log"
    isolated_root = tmp_path / "isolated-sidecar-root"
    isolated_root.mkdir()
    captured_cargo_command: list[str] = []
    captured_proof_command: list[str] = []
    captured_cargo_env: dict[str, str] = {}
    captured_proof_env: dict[str, str] = {}

    class _FakeTempDir:
        def __init__(self, name: str):
            self.name = name
            self.cleaned = False

        def cleanup(self):
            self.cleaned = True

    fake_temp_dir = _FakeTempDir(str(isolated_root))

    class _FakeProcess:
        def poll(self):
            return 0

        def terminate(self):
            return None

        def wait(self, timeout=None):
            return 0

        def kill(self):
            return None

    monkeypatch.setattr(
        proof_sidecar,
        "_parse_args",
        lambda: argparse.Namespace(
            port=3032,
            service_url="",
            ready_timeout=1.0,
            data_dir=None,
            log_path=log_path,
        ),
    )
    monkeypatch.setattr(proof_sidecar, "_check_health", lambda url: False)
    monkeypatch.setattr(proof_sidecar, "_port_is_available", lambda port: True)
    monkeypatch.setattr(
        proof_sidecar,
        "_wait_for_health",
        lambda url, timeout_seconds: True,
    )
    monkeypatch.setattr(
        proof_sidecar.tempfile,
        "TemporaryDirectory",
        lambda prefix: fake_temp_dir,
    )

    def _fake_popen(command, **kwargs):
        captured_cargo_command.extend(command)
        captured_cargo_env.update(kwargs["env"])
        return _FakeProcess()

    def _fake_run(command, **kwargs):
        captured_proof_command.extend(command)
        captured_proof_env.update(kwargs["env"])
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(proof_sidecar.subprocess, "Popen", _fake_popen)
    monkeypatch.setattr(proof_sidecar.subprocess, "run", _fake_run)

    result = proof_sidecar.main()

    assert result == 0
    assert captured_cargo_command == [
        "cargo",
        "run",
        "--manifest-path",
        "memvid_service/Cargo.toml",
        "--release",
    ]
    assert captured_cargo_env["MEMORY_SERVICE_PORT"] == "3032"
    assert captured_cargo_env["MEMORY_DATA_DIR"] == str(isolated_root)
    assert captured_proof_command == [
        sys.executable,
        "scripts/run_tests.py",
        "--sidecar",
    ]
    assert captured_proof_env["MEMORY_SERVICE_PORT"] == "3032"
    assert captured_proof_env["MEMORY_SERVICE_URL"] == "http://localhost:3032"
    assert captured_proof_env["MEMORY_DATA_DIR"] == str(isolated_root)
    assert captured_proof_env["RUN_MEMVID_TESTS"] == "1"
    assert captured_proof_env["MEMORY_BACKEND"] == "rust"
    assert fake_temp_dir.cleaned is True


@pytest.mark.fixture_drift
def test_generated_frontend_api_fixtures_match_backend_export(tmp_path):
    generated_path = tmp_path / "api.fixtures.generated.json"
    committed_path = (
        ROOT / "frontend" / "src" / "lib" / "api.fixtures.generated.json"
    )

    subprocess.run(
        [sys.executable, "scripts/export_api_fixtures.py", "--output", str(generated_path)],
        cwd=ROOT,
        check=True,
    )

    generated = json.loads(generated_path.read_text(encoding="utf-8"))
    committed = json.loads(committed_path.read_text(encoding="utf-8"))

    assert generated == committed
    assert_contract_payload("GET /api/subsystems", committed["SUBSYSTEMS_FIXTURE"])
    assert_contract_payload("GET /api/hca/runs", committed["RUN_LIST_FIXTURE"])
    assert_contract_payload("GET /api/hca/run/{run_id}", committed["RUN_SUMMARY_FIXTURE"])
    assert_contract_payload(
        "POST /api/hca/run/{run_id}/approve",
        committed["RUN_APPROVED_SUMMARY_FIXTURE"],
    )
    assert_contract_payload(
        "GET /api/hca/run/{run_id}/events",
        committed["RUN_EVENTS_FIXTURE"],
    )
    assert_contract_payload(
        "GET /api/hca/run/{run_id}/artifacts",
        committed["RUN_ARTIFACTS_FIXTURE"],
    )
    assert_contract_payload(
        "GET /api/hca/run/{run_id}/artifacts/{artifact_id}",
        committed["RUN_ARTIFACT_DETAIL_FIXTURE"],
    )
    assert_contract_payload(
        "GET /api/hca/memory/list",
        committed["MEMORY_LIST_FIXTURE"],
    )
    assert_contract_payload(
        "DELETE /api/hca/memory/{memory_id}",
        committed["DELETE_MEMORY_FIXTURE"],
    )
