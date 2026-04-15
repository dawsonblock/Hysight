import logging
import os
from dataclasses import dataclass
from typing import Any, Optional

from fastapi import HTTPException


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


def load_backend_settings() -> BackendSettings:
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


async def initialize_database(settings: BackendSettings) -> None:
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
            "backend/requirements-integration.txt"
        ) from exc

    try:
        client = AsyncIOMotorClient(
            settings.mongo_url,
            serverSelectionTimeoutMS=2000,
        )
        await client.admin.command("ping")
    except Exception as exc:  # pragma: no cover
        close_database()
        raise BackendConfigurationError(
            "Configured MongoDB connection could not be established. "
            "Verify MONGO_URL, DB_NAME, network reachability, and "
            f"credentials. ({exc})"
        ) from exc

    db = client[settings.db_name]


def close_database() -> None:
    global client, db
    if client is not None:
        client.close()
    client = None
    db = None


def require_db() -> Any:
    if db is None:
        raise HTTPException(
            status_code=503,
            detail="Database is not initialized",
        )
    return db


def get_client() -> Any:
    return client


def get_db() -> Any:
    return db