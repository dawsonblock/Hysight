import os
import tempfile
from pathlib import Path

from backend.server_models import (
    DatabaseSubsystemStatus,
    LLMSubsystemStatus,
    MemorySubsystemStatus,
    StorageSubsystemStatus,
    SubsystemsResponse,
)
from backend.server_persistence import (
    get_client,
    get_db,
    load_backend_settings,
)
from hca.paths import storage_root  # noqa: E402
from memory_service.config import (
    MemoryConfigurationError,
    load_memory_settings,
    probe_memory_service,
)


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


async def get_subsystems() -> SubsystemsResponse:
    settings = load_backend_settings()
    client = get_client()
    db = get_db()

    if not settings.database_enabled:
        database_status = DatabaseSubsystemStatus(
            enabled=False,
            status="disabled",
            detail=(
                "Mongo-backed /api/status persistence is disabled because "
                "MONGO_URL and DB_NAME are unset. Replay-backed HCA and "
                "memory routes remain available without Mongo."
            ),
        )
    elif client is None or db is None:
        database_status = DatabaseSubsystemStatus(
            enabled=True,
            status="unhealthy",
            detail=(
                "Mongo is configured for optional /api/status persistence, "
                "but the backend database client is unavailable."
            ),
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
                detail=(
                    "Mongo-backed /api/status persistence is reachable. "
                    "Mongo does not own replay-backed HCA or memory routes."
                ),
            )

    memory_settings = None
    try:
        memory_settings = load_memory_settings()
    except MemoryConfigurationError as exc:
        memory_status = MemorySubsystemStatus(
            backend="unknown",
            uses_sidecar=False,
            status="unhealthy",
            detail=f"Memory authority configuration is invalid: {exc}",
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
                    detail=(
                        "Rust memory sidecar is configured as the active "
                        f"memory authority but is unavailable: {exc}"
                    ),
                    service_url=memory_settings.service_url,
                )
            else:
                memory_status = MemorySubsystemStatus(
                    backend=memory_settings.backend,
                    uses_sidecar=True,
                    status="healthy",
                    detail=(
                        "Rust memory sidecar is the active memory authority "
                        "and is reachable"
                    ),
                    service_url=memory_settings.service_url,
                )
        else:
            memory_status = MemorySubsystemStatus(
                backend=memory_settings.backend,
                uses_sidecar=False,
                status="healthy",
                detail=(
                    "Python in-process memory controller is the active "
                    "local memory authority"
                ),
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