import logging
import os
import tempfile
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from fastapi import APIRouter, FastAPI, HTTPException, Query
from starlette.middleware.cors import CORSMiddleware

from backend import server_bootstrap as _server_bootstrap  # noqa: F401
from backend.server_models import (
    DatabaseSubsystemStatus,
    LLMSubsystemStatus,
    MemorySubsystemStatus,
    StorageSubsystemStatus,
    SubsystemsResponse,
)
from backend.server_hca_routes import register_hca_routes
from backend.server_memory_routes import register_memory_routes
from backend.server_status_routes import register_status_routes
from memory_service.config import (
    MemoryConfigurationError,
    load_memory_settings,
    probe_memory_service,
    validate_memory_backend_startup,
)
from hca.paths import storage_root  # noqa: E402

logger = logging.getLogger(__name__)
client: Any = None
db: Any = None


class BackendConfigurationError(RuntimeError):
    """Raised when required backend configuration is missing."""


@dataclass(frozen=True)
class BackendSettings:
    mongo_url: Optional[str] = None
    db_name: Optional[str] = None

    @property
    def database_enabled(self) -> bool:
        return bool(self.mongo_url and self.db_name)


def _load_settings() -> BackendSettings:
    mongo_url = os.environ.get("MONGO_URL", "").strip()
    db_name = os.environ.get("DB_NAME", "").strip()
    if not mongo_url and not db_name:
        return BackendSettings()

    missing = []
    if not mongo_url:
        missing.append("MONGO_URL")
    if not db_name:
        missing.append("DB_NAME")
    if missing:
        joined = ", ".join(missing)
        raise BackendConfigurationError(
            "Mongo configuration is partial; set both MONGO_URL and "
            "DB_NAME or unset both to run without database integration. "
            f"Missing: {joined}. Example: MONGO_URL=mongodb://localhost:27017 "
            "DB_NAME=hysight"
        )

    return BackendSettings(mongo_url=mongo_url, db_name=db_name)


def _load_cors_origins() -> List[str]:
    raw_origins = os.environ.get("CORS_ORIGINS", "").strip()
    if not raw_origins:
        return []

    origins = [
        origin.strip() for origin in raw_origins.split(",") if origin.strip()
    ]
    if not origins:
        return []
    if "*" in origins:
        raise BackendConfigurationError(
            "CORS_ORIGINS cannot contain '*' when credentials are enabled; "
            "provide a comma-separated allowlist such as "
            "http://localhost:3000,https://app.example.com"
        )

    invalid = []
    for origin in origins:
        parsed = urlparse(origin)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            invalid.append(origin)
    if invalid:
        joined = ", ".join(invalid)
        raise BackendConfigurationError(
            "CORS_ORIGINS must contain absolute http(s) origins such as "
            f"http://localhost:3000: {joined}"
        )

    return origins


async def _initialize_database(settings: BackendSettings) -> None:
    global client, db
    if not settings.database_enabled:
        logger.info(
            "Database integration disabled — /status routes will return 503 "
            "until both MONGO_URL and DB_NAME are configured."
        )
        client = None
        db = None
        return

    try:
        from motor.motor_asyncio import AsyncIOMotorClient
    except ImportError as exc:
        raise BackendConfigurationError(
            "motor must be installed when MONGO_URL and DB_NAME are "
            "configured. Run: python -m pip install -r "
            "backend/requirements.txt"
        ) from exc

    try:
        client = AsyncIOMotorClient(
            settings.mongo_url,
            serverSelectionTimeoutMS=2000,
        )
        await client.admin.command("ping")
    except Exception as exc:  # pragma: no cover
        if client is not None:
            client.close()
        client = None
        db = None
        raise BackendConfigurationError(
            "Configured MongoDB connection could not be established. "
            "Verify MONGO_URL, DB_NAME, network reachability, and "
            f"credentials. ({exc})"
        ) from exc

    db = client[settings.db_name]


def _require_db() -> Any:
    if db is None:
        raise HTTPException(
            status_code=503,
            detail="Database is not initialized",
        )
    return db


def _probe_directory_writable(path: Path) -> tuple[str, str]:
    try:
        path.mkdir(parents=True, exist_ok=True)
        fd, probe_path = tempfile.mkstemp(
            prefix=".hysight-probe-",
            dir=path,
            text=True,
        )
        os.close(fd)
        os.unlink(probe_path)
    except Exception as exc:
        return "unavailable", f"{exc.__class__.__name__}: {exc}"

    return "writable", f"{path}"


def _overall_subsystem_status(
    database: DatabaseSubsystemStatus,
    memory: MemorySubsystemStatus,
    storage: StorageSubsystemStatus,
    llm: LLMSubsystemStatus,
) -> str:
    if (
        database.status == "unhealthy"
        or memory.status == "unhealthy"
        or storage.status == "unavailable"
    ):
        return "unhealthy"
    if database.status == "disabled" or llm.status == "missing":
        return "degraded"
    return "healthy"


async def _get_subsystems() -> SubsystemsResponse:
    settings = _load_settings()

    if not settings.database_enabled:
        database_status = DatabaseSubsystemStatus(
            enabled=False,
            status="disabled",
            detail=(
                "Mongo-backed /api/status persistence is disabled because "
                "MONGO_URL and DB_NAME are unset"
            ),
        )
    elif client is None or db is None:
        database_status = DatabaseSubsystemStatus(
            enabled=True,
            status="unhealthy",
            detail="Mongo is configured but the backend database client is unavailable",
        )
    else:
        try:
            await client.admin.command("ping")
        except Exception as exc:
            database_status = DatabaseSubsystemStatus(
                enabled=True,
                status="unhealthy",
                detail=f"Mongo ping failed: {exc}",
            )
        else:
            database_status = DatabaseSubsystemStatus(
                enabled=True,
                status="healthy",
                detail="Mongo-backed /api/status persistence is reachable",
            )

    memory_settings = None
    try:
        memory_settings = load_memory_settings()
    except MemoryConfigurationError as exc:
        memory_status = MemorySubsystemStatus(
            backend="unknown",
            uses_sidecar=False,
            status="unhealthy",
            detail=str(exc),
            service_url=None,
        )
    else:
        if memory_settings.uses_sidecar:
            try:
                probe_memory_service(memory_settings, timeout=2.0)
            except MemoryConfigurationError as exc:
                memory_status = MemorySubsystemStatus(
                    backend=memory_settings.backend,
                    uses_sidecar=True,
                    status="unhealthy",
                    detail=str(exc),
                    service_url=memory_settings.service_url,
                )
            else:
                memory_status = MemorySubsystemStatus(
                    backend=memory_settings.backend,
                    uses_sidecar=True,
                    status="healthy",
                    detail="Rust memory sidecar is reachable",
                    service_url=memory_settings.service_url,
                )
        else:
            memory_status = MemorySubsystemStatus(
                backend=memory_settings.backend,
                uses_sidecar=False,
                status="healthy",
                detail="Python in-process memory backend is active",
                service_url=None,
            )

    try:
        root_path = storage_root()
    except Exception as exc:
        storage_status = StorageSubsystemStatus(
            status="unavailable",
            detail=f"Storage root is invalid: {exc}",
            root=os.environ.get("HCA_STORAGE_ROOT", ""),
            memory_dir=(
                str(memory_settings.storage_dir)
                if memory_settings is not None
                else os.environ.get("MEMORY_STORAGE_DIR", "")
            ),
        )
    else:
        memory_dir = (
            memory_settings.storage_dir
            if memory_settings is not None
            else root_path / "memory"
        )
        root_probe_status, root_detail = _probe_directory_writable(root_path)
        memory_probe_status, memory_detail = _probe_directory_writable(
            memory_dir
        )
        storage_status = StorageSubsystemStatus(
            status=(
                "writable"
                if root_probe_status == "writable"
                and memory_probe_status == "writable"
                else "unavailable"
            ),
            detail=(
                "HCA storage root and memory storage are writable"
                if root_probe_status == "writable"
                and memory_probe_status == "writable"
                else (
                    "storage_root="
                    f"{root_detail}; memory_dir={memory_detail}"
                )
            ),
            root=str(root_path),
            memory_dir=str(memory_dir),
        )

    llm_key = os.environ.get("EMERGENT_LLM_KEY", "").strip()
    llm_status = LLMSubsystemStatus(
        status="configured" if llm_key else "missing",
        detail=(
            "EMERGENT_LLM_KEY is configured"
            if llm_key
            else "EMERGENT_LLM_KEY is missing; LLM-backed modules will fall back when possible"
        ),
    )

    return SubsystemsResponse(
        status=_overall_subsystem_status(
            database_status,
            memory_status,
            storage_status,
            llm_status,
        ),
        database=database_status,
        memory=memory_status,
        storage=storage_status,
        llm=llm_status,
    )


api_router = APIRouter(prefix="/api")
register_status_routes(
    api_router,
    require_db=_require_db,
    get_subsystems=_get_subsystems,
)
register_hca_routes(api_router)
register_memory_routes(api_router)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    settings = _load_settings()
    memory_settings = validate_memory_backend_startup()
    logger.info(
        (
            "Memory authority configured — backend=%s storage_dir=%s "
            "service_url=%s run_storage_root=%s"
        ),
        memory_settings.backend,
        memory_settings.storage_dir,
        memory_settings.service_url or "disabled",
        storage_root(),
    )
    await _initialize_database(settings)
    try:
        yield
    finally:
        global client, db
        if client is not None:
            client.close()
        client = None
        db = None


def create_app() -> FastAPI:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    cors_origins = _load_cors_origins()
    application = FastAPI(title="HCA API", lifespan=_lifespan)
    application.include_router(api_router)
    application.add_middleware(
        CORSMiddleware,
        allow_credentials=True,
        allow_origins=cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    return application


app = create_app()
