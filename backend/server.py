import logging
import os
from contextlib import asynccontextmanager
from typing import List
from urllib.parse import urlparse

from fastapi import APIRouter, FastAPI
from starlette.middleware.cors import CORSMiddleware

from backend import server_bootstrap as _server_bootstrap  # noqa: F401
from backend import server_persistence, server_subsystems
from backend.server_autonomy_routes import register_autonomy_routes
from backend.server_hca_routes import register_hca_routes
from backend.server_memory_routes import register_memory_routes
from backend.server_status_routes import register_status_routes
from memory_service.config import validate_memory_backend_startup
from hca.paths import storage_root  # noqa: E402

logger = logging.getLogger(__name__)


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
        raise server_persistence.BackendConfigurationError(
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
        raise server_persistence.BackendConfigurationError(
            "CORS_ORIGINS must contain absolute http(s) origins such as "
            f"http://localhost:3000: {joined}"
        )

    return origins
api_router = APIRouter(prefix="/api")
register_status_routes(
    api_router,
    require_db=server_persistence.require_db,
    get_subsystems=server_subsystems.get_subsystems,
)
register_hca_routes(api_router)
register_memory_routes(api_router)
register_autonomy_routes(api_router)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    settings = server_persistence.load_backend_settings()
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
    await server_persistence.initialize_database(settings)
    # Optional background supervisor loop. Disabled by default so tests and
    # ephemeral dev processes never spawn a thread. Enable with
    # AUTONOMY_LOOP_ENABLED=1 plus an optional AUTONOMY_LOOP_INTERVAL=<secs>.
    loop_started = False
    if os.getenv("AUTONOMY_LOOP_ENABLED") == "1":
        try:
            from hca.autonomy.supervisor import get_supervisor

            interval = float(os.getenv("AUTONOMY_LOOP_INTERVAL", "5.0"))
            loop_started = get_supervisor().start_loop(interval_seconds=interval)
            if loop_started:
                logger.info(
                    "Autonomy supervisor loop started (interval=%.1fs)", interval
                )
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Autonomy supervisor loop failed to start: %s", exc)
    try:
        yield
    finally:
        if loop_started:
            try:
                from hca.autonomy.supervisor import get_supervisor

                get_supervisor().stop_loop(timeout_seconds=5.0)
                logger.info("Autonomy supervisor loop stopped")
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Autonomy supervisor loop stop failed: %s", exc)
        server_persistence.close_database()


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
