import asyncio
import concurrent.futures
import json
import logging
import os
import sys
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib import import_module
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.cors import CORSMiddleware
from memory_service import (
    DeleteMemoryResponse,
    MaintenanceReport,
    MemoryConfigurationError,
    MemoryListResponse,
    RetrievalQuery,
    RetrievalResponse,
)
from memory_service.config import validate_memory_backend_startup
from memory_service.controller import MemoryBackendError
from memory_service.types import MemoryType, ScopeType

ROOT_DIR = Path(__file__).resolve().parent
REPO_ROOT = ROOT_DIR.parent
HCA_SRC_DIR = REPO_ROOT / "hca" / "src"

for path in (str(REPO_ROOT), str(HCA_SRC_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from hca.api.models import (  # type: ignore[import-untyped]  # noqa: E402
    ApprovalSelectionRequest,
    CreateRunRequest,
)

_run_views = import_module("hca.api.run_views")
HCARunArtifactDetailResponse = _run_views.RunArtifactDetailResponse
HCARunArtifactListResponse = _run_views.RunArtifactListResponse
HCARunEventListResponse = _run_views.RunEventListResponse
HCARunListResponse = _run_views.RunListResponse
HCARunSummaryResponse = _run_views.RunSummaryResponse
_extract_run_summary = _run_views.extract_run_summary
get_run_artifact_detail = _run_views.get_run_artifact_detail
list_run_artifacts = _run_views.list_run_artifacts
list_run_events = _run_views.list_run_events
_list_run_summaries = _run_views.list_run_summaries
_require_run_context = _run_views.require_run_context

load_dotenv(ROOT_DIR / ".env")

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


# Pydantic models.


class BackendModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class APIRootResponse(BackendModel):
    message: str


class StatusCheck(BackendModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class StatusCheckCreate(BackendModel):
    client_name: str


# Status endpoints.

@api_router.get("/", response_model=APIRootResponse)
async def root():
    return APIRootResponse(message="HCA API — Hybrid Cognitive Agent")


@api_router.post("/status", response_model=StatusCheck)
async def create_status_check(input: StatusCheckCreate):
    database = _require_db()
    status_obj = StatusCheck(**input.model_dump())
    doc = status_obj.model_dump()
    doc["timestamp"] = doc["timestamp"].isoformat()
    await database.status_checks.insert_one(doc)
    return status_obj


@api_router.get("/status", response_model=List[StatusCheck])
async def get_status_checks():
    database = _require_db()
    checks = await database.status_checks.find({}, {"_id": 0}).to_list(1000)
    for c in checks:
        if isinstance(c.get("timestamp"), str):
            c["timestamp"] = datetime.fromisoformat(c["timestamp"])
    return checks


# HCA endpoints.

@api_router.get("/hca/runs", response_model=HCARunListResponse)
async def list_hca_runs(
    q: Optional[str] = Query(default=None, max_length=200),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """List recent runs with replay-backed summaries."""
    return _list_run_summaries(limit=limit, offset=offset, query_text=q)


@api_router.post("/hca/run", response_model=HCARunSummaryResponse)
async def run_hca(body: CreateRunRequest):
    """Submit a goal to the HCA and return the run result."""
    from hca.runtime.runtime import Runtime  # type: ignore

    def _execute():
        rt = Runtime()
        return rt.run(body.goal, user_id=body.user_id)

    run_id = await asyncio.to_thread(_execute)
    return _extract_run_summary(run_id)


# Readable labels for each HCA event type in the streaming trace
_STREAM_LABELS: Dict[str, str] = {
    "run_created":        "Run initialised",
    "module_proposed":    "Module proposed",
    "meta_assessed":      "Workspace assessed",
    "action_scored":      "Actions scored",
    "action_selected":    "Action selected",
    "approval_requested": "Approval required",
    "execution_started":  "Executing action",
    "execution_finished": "Execution finished",
    "memory_written":     "Memory written",
    "run_completed":      "Run completed",
    "run_failed":         "Run failed",
    "snapshot_saved":     "Snapshot saved",
}


def _stream_label(ev: Dict[str, Any]) -> str:
    et = ev.get("event_type", "")
    actor = ev.get("actor", "")
    payload = ev.get("payload", {})
    base = _STREAM_LABELS.get(et, et.replace("_", " "))
    if et == "module_proposed":
        src = payload.get("source_module") or actor
        ci = payload.get("candidate_items", [])
        kinds = list({c.get("kind", "") for c in ci if c.get("kind")})
        detail = f"{src}: {', '.join(kinds)}" if kinds else src
        return f"{base} — {detail}"
    if et == "action_selected":
        kind = payload.get("kind", "?")
        return f"{base}: {kind}"
    if et == "execution_finished":
        status = payload.get("status", "?")
        return f"{base} ({status})"
    if et == "approval_requested":
        return f"{base} — action needs your sign-off"
    return base


def _sse(event_type: str, data: Any) -> str:
    def _json_default(value: Any):
        if isinstance(value, BaseModel):
            return value.model_dump(mode="json")
        return str(value)

    payload = json.dumps(data, default=_json_default)
    return f"event: {event_type}\ndata: {payload}\n\n"


@api_router.post("/hca/run/stream")
async def stream_hca_run(body: CreateRunRequest):
    """Stream HCA pipeline events as Server-Sent Events (SSE).

    Each event payload has the shape:
      { "step": <int>, "event_type": <str>, "label": <str>,
        "actor": <str>, "timestamp": <iso>, "payload": {...} }
    Final 'done' event contains the full run summary.
    """
    result_holder: Dict[str, Any] = {
        "run_id": None,
        "done": False,
        "error": None,
    }

    def _execute():
        from hca.runtime.runtime import Runtime  # type: ignore

        class _StreamingRuntime(Runtime):
            """Captures run_id as early as possible via _step_create hook."""
            def _step_create(self, goal, user_id=None):
                ctx = super()._step_create(goal, user_id)
                result_holder["run_id"] = ctx.run_id
                return ctx

        try:
            rt = _StreamingRuntime()
            run_id = rt.run(body.goal, user_id=body.user_id)
            result_holder["run_id"] = run_id
        except Exception as exc:
            result_holder["error"] = str(exc)
        finally:
            result_holder["done"] = True

    _executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

    async def generate():
        from hca.storage import iter_events  # type: ignore

        # Kick off the HCA thread
        loop = asyncio.get_event_loop()
        future = loop.run_in_executor(_executor, _execute)

        yield _sse("status", {"label": "Connecting to agent…", "step": 0})

        last_event_count = 0
        run_id: Optional[str] = None
        step = 1

        # Stream loop — poll every 300 ms until HCA finishes
        while not result_holder["done"]:
            await asyncio.sleep(0.3)

            # Pick up run_id as soon as it's available
            if not run_id and result_holder["run_id"]:
                run_id = result_holder["run_id"]
                yield _sse(
                    "status",
                    {
                        "label": "Pipeline running…",
                        "step": step,
                        "run_id": run_id,
                    },
                )
                step += 1

            if run_id:
                events = list(iter_events(run_id))
                for ev in events[last_event_count:]:
                    label = _stream_label(ev)
                    yield _sse("step", {
                        "step":       step,
                        "event_type": ev.get("event_type"),
                        "label":      label,
                        "actor":      ev.get("actor"),
                        "timestamp":  ev.get("timestamp"),
                        "payload":    ev.get("payload", {}),
                    })
                    step += 1
                last_event_count = len(events)

        # Await thread completion (already done, just joins)
        await asyncio.wait_for(asyncio.wrap_future(future), timeout=5.0)

        if result_holder["error"]:
            yield _sse("error", {"label": result_holder["error"]})
            return

        run_id = result_holder["run_id"]
        if run_id:
            # Flush any remaining events
            from hca.storage import iter_events  # type: ignore
            events = list(iter_events(run_id))
            for ev in events[last_event_count:]:
                label = _stream_label(ev)
                yield _sse("step", {
                    "step":       step,
                    "event_type": ev.get("event_type"),
                    "label":      label,
                    "actor":      ev.get("actor"),
                    "timestamp":  ev.get("timestamp"),
                    "payload":    ev.get("payload", {}),
                })
                step += 1

            summary = _extract_run_summary(run_id)
            yield _sse("done", summary)
        else:
            yield _sse("error", {"label": "Run failed to start."})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection":    "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@api_router.get("/hca/run/{run_id}", response_model=HCARunSummaryResponse)
async def get_hca_run(run_id: str):
    """Fetch current state of an HCA run."""
    _require_run_context(run_id)
    return _extract_run_summary(run_id)


@api_router.get(
    "/hca/run/{run_id}/events",
    response_model=HCARunEventListResponse,
)
async def list_hca_run_events(
    run_id: str,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """List bounded, newest-first events for a run."""
    return list_run_events(run_id, limit=limit, offset=offset)


@api_router.get(
    "/hca/run/{run_id}/artifacts",
    response_model=HCARunArtifactListResponse,
)
async def list_hca_run_artifacts(
    run_id: str,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """List bounded, newest-first artifact records for a run."""
    return list_run_artifacts(run_id, limit=limit, offset=offset)


@api_router.get(
    "/hca/run/{run_id}/artifacts/{artifact_id}",
    response_model=HCARunArtifactDetailResponse,
)
async def get_hca_run_artifact(
    run_id: str,
    artifact_id: str,
    preview_bytes: int = Query(default=20000, ge=1, le=200000),
):
    """Fetch a single artifact record with bounded text content preview."""
    return get_run_artifact_detail(
        run_id,
        artifact_id,
        preview_bytes=preview_bytes,
    )


@api_router.post(
    "/hca/run/{run_id}/approve",
    response_model=HCARunSummaryResponse,
)
async def approve_hca_action(
    run_id: str,
    body: ApprovalSelectionRequest,
):
    """Grant approval for a pending HCA action and resume execution."""
    from hca.runtime.runtime import Runtime  # type: ignore
    from hca.storage import load_run  # type: ignore
    from hca.storage.approvals import append_grant  # type: ignore
    from hca.common.types import ApprovalGrant  # type: ignore

    context = load_run(run_id)
    if not context:
        raise HTTPException(status_code=404, detail="Run not found")

    token = str(uuid.uuid4())
    approval_id = body.approval_id

    def _approve_and_resume():
        append_grant(
            run_id,
            ApprovalGrant(approval_id=approval_id, token=token),
        )
        rt = Runtime()
        rt._current_state = context.state
        return rt.resume(run_id, approval_id, token)

    new_run_id = await asyncio.to_thread(_approve_and_resume)
    return _extract_run_summary(new_run_id)


@api_router.post(
    "/hca/run/{run_id}/deny",
    response_model=HCARunSummaryResponse,
)
async def deny_hca_action(
    run_id: str,
    body: ApprovalSelectionRequest,
):
    """Deny a pending HCA action."""
    from hca.runtime.runtime import Runtime  # type: ignore
    from hca.storage import load_run  # type: ignore

    context = load_run(run_id)
    if not context:
        raise HTTPException(status_code=404, detail="Run not found")

    def _deny():
        rt = Runtime()
        rt._current_state = context.state
        return rt.deny_approval(
            run_id,
            body.approval_id,
            reason="Denied by user",
        )

    new_run_id = await asyncio.to_thread(_deny)
    return _extract_run_summary(new_run_id)


@api_router.post("/hca/memory/retrieve", response_model=RetrievalResponse)
async def retrieve_memory(body: RetrievalQuery):
    """Retrieve memories matching a natural-language query."""
    from memory_service.singleton import get_controller  # type: ignore

    try:
        return RetrievalResponse(hits=get_controller().retrieve(body))
    except (MemoryBackendError, MemoryConfigurationError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@api_router.post("/hca/memory/maintain", response_model=MaintenanceReport)
async def maintain_memory():
    """Run memory maintenance (TTL expiry)."""
    from memory_service.singleton import get_controller  # type: ignore

    try:
        return get_controller().maintain()
    except (MemoryBackendError, MemoryConfigurationError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@api_router.get("/hca/memory/list", response_model=MemoryListResponse)
async def list_memory(
    memory_type: Optional[MemoryType] = None,
    scope: Optional[ScopeType] = None,
    include_expired: bool = False,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """List stored memories with optional filtering, newest first."""
    from memory_service.singleton import get_controller  # type: ignore

    try:
        records, total = get_controller().list_records(
            memory_type=memory_type,
            scope=scope,
            include_expired=include_expired,
            limit=limit,
            offset=offset,
        )
    except (MemoryBackendError, MemoryConfigurationError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return MemoryListResponse(records=records, total=total)


@api_router.delete(
    "/hca/memory/{memory_id}",
    response_model=DeleteMemoryResponse,
)
async def delete_memory(memory_id: str):
    """Delete a memory record by ID."""
    from memory_service.singleton import get_controller  # type: ignore

    try:
        deleted = get_controller().delete_record(memory_id)
    except (MemoryBackendError, MemoryConfigurationError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Memory not found")
    return DeleteMemoryResponse(deleted=True, memory_id=memory_id)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    global client, db
    settings = _load_settings()
    validate_memory_backend_startup()
    await _initialize_database(settings)
    yield
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
