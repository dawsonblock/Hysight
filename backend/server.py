import logging
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from fastapi import APIRouter, FastAPI, HTTPException, Query
from starlette.middleware.cors import CORSMiddleware

from backend import server_bootstrap as _server_bootstrap  # noqa: F401
from backend.server_hca_routes import register_hca_routes
from backend.server_memory_routes import register_memory_routes
from backend.server_status_routes import register_status_routes
from memory_service.config import validate_memory_backend_startup
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


api_router = APIRouter(prefix="/api")
register_status_routes(api_router, require_db=_require_db)
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
