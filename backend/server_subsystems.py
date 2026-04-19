import os
import tempfile
from pathlib import Path

from backend.server_models import (
    AutonomySubsystemStatus,
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
from hca.autonomy.supervisor import get_supervisor
from hca.paths import storage_root  # noqa: E402
from memory_service.config import (
    MemoryConfigurationError,
    load_memory_settings,
    probe_memory_service,
)


REPLAY_AUTHORITY = "local_store"
HCA_RUNTIME_AUTHORITY = "python_hca_runtime"
MONGO_SCOPE = "status_only"


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
    mongo_connected = False

    if not settings.database_enabled:
        database_status = DatabaseSubsystemStatus(
            enabled=False,
            status="disabled",
            mongo_status_mode="disabled",
            mongo_scope=MONGO_SCOPE,
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
            mongo_status_mode="configured_unreachable",
            mongo_scope=MONGO_SCOPE,
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
                mongo_status_mode="configured_unreachable",
                mongo_scope=MONGO_SCOPE,
                detail=f"Mongo ping failed: {exc}",
            )
        else:
            mongo_connected = True
            database_status = DatabaseSubsystemStatus(
                enabled=True,
                status="healthy",
                mongo_status_mode="connected",
                mongo_scope=MONGO_SCOPE,
                detail=(
                    "Mongo-backed /api/status persistence is reachable. "
                    "Mongo does not own replay-backed HCA or memory routes."
                ),
            )

    memory_settings = None
    sidecar_reachable = False
    try:
        memory_settings = load_memory_settings()
    except MemoryConfigurationError as exc:
        memory_status = MemorySubsystemStatus(
            backend="unknown",
            uses_sidecar=False,
            status="unhealthy",
            memory_backend_mode="unavailable",
            service_available=None,
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
                    memory_backend_mode="sidecar",
                    service_available=False,
                    detail=(
                        "Rust memory sidecar is configured as the active "
                        f"memory authority at {memory_settings.service_url} "
                        f"but is unavailable: {exc}"
                    ),
                    service_url=memory_settings.service_url,
                )
            else:
                sidecar_reachable = True
                memory_status = MemorySubsystemStatus(
                    backend=memory_settings.backend,
                    uses_sidecar=True,
                    status="healthy",
                    memory_backend_mode="sidecar",
                    service_available=True,
                    detail=(
                        "Rust memory sidecar is the active memory authority "
                        f"at {memory_settings.service_url} and is reachable"
                    ),
                    service_url=memory_settings.service_url,
                )
        else:
            memory_status = MemorySubsystemStatus(
                backend=memory_settings.backend,
                uses_sidecar=False,
                status="healthy",
                memory_backend_mode="local",
                service_available=None,
                detail=(
                    "Python in-process memory controller is the active "
                    f"local memory authority at {memory_settings.storage_dir}"
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

    if not settings.database_enabled:
        database_consistent = (
            database_status.status == "disabled"
            and database_status.mongo_status_mode == "disabled"
        )
    else:
        database_consistent = (
            mongo_connected
            and database_status.status == "healthy"
            and database_status.mongo_status_mode == "connected"
        ) or (
            not mongo_connected
            and database_status.status == "unhealthy"
            and database_status.mongo_status_mode == "configured_unreachable"
        )

    if memory_settings is None:
        memory_consistent = False
    elif memory_settings.uses_sidecar:
        memory_consistent = (
            memory_status.memory_backend_mode == "sidecar"
            and memory_status.service_available is sidecar_reachable
            and memory_status.service_url == memory_settings.service_url
        )
    else:
        memory_consistent = (
            memory_status.memory_backend_mode == "local"
            and memory_status.service_available is None
            and memory_status.service_url is None
        )

    return SubsystemsResponse(
        status=_overall_subsystem_status(
            database_status,
            memory_status,
            storage_status,
            llm_status,
        ),
        consistency_check_passed=database_consistent and memory_consistent,
        replay_authority=REPLAY_AUTHORITY,
        hca_runtime_authority=HCA_RUNTIME_AUTHORITY,
        database=database_status,
        memory=memory_status,
        storage=storage_status,
        llm=llm_status,
        autonomy=_autonomy_status(),
    )


def _autonomy_status() -> AutonomySubsystemStatus:
    try:
        supervisor = get_supervisor()
        status = supervisor.status()
        return AutonomySubsystemStatus(**status.model_dump(mode="json"))
    except Exception as exc:  # pragma: no cover - defensive
        return AutonomySubsystemStatus(
            enabled=False,
            running=False,
            active_agents=0,
            active_runs=0,
            pending_triggers=0,
            loop_running=False,
            kill_switch_active=False,
            kill_switch_reason=None,
            kill_switch_set_at=None,
            last_tick_at=None,
            last_error=f"{exc.__class__.__name__}: {exc}",
        )