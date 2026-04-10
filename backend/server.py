import asyncio
import concurrent.futures
import json
import logging
import os
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.cors import CORSMiddleware


ROOT_DIR = Path(__file__).resolve().parent
REPO_ROOT = ROOT_DIR.parent
HCA_SRC_DIR = REPO_ROOT / "hca" / "src"

for path in (str(REPO_ROOT), str(HCA_SRC_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

load_dotenv(ROOT_DIR / ".env")

logger = logging.getLogger(__name__)
client: Any = None
db: Any = None


class BackendConfigurationError(RuntimeError):
    """Raised when required backend configuration is missing."""


@dataclass(frozen=True)
class BackendSettings:
    mongo_url: str
    db_name: str


def _load_settings() -> BackendSettings:
    missing = [
        name for name in ("MONGO_URL", "DB_NAME") if not os.environ.get(name)
    ]
    if missing:
        joined = ", ".join(missing)
        raise BackendConfigurationError(
            f"Missing required backend settings: {joined}"
        )
    return BackendSettings(
        mongo_url=os.environ["MONGO_URL"],
        db_name=os.environ["DB_NAME"],
    )


def _require_db() -> Any:
    if db is None:
        raise HTTPException(
            status_code=503,
            detail="Database is not initialized",
        )
    return db


api_router = APIRouter(prefix="/api")

# ── Pydantic models ───────────────────────────────────────────────────────────

class StatusCheck(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class StatusCheckCreate(BaseModel):
    client_name: str


class HCARunRequest(BaseModel):
    goal: str
    user_id: Optional[str] = None


class HCAApproveRequest(BaseModel):
    approval_id: str


class MemoryQueryRequest(BaseModel):
    query: str
    top_k: int = 10
    run_id: Optional[str] = None


# ── Status endpoints ──────────────────────────────────────────────────────────

@api_router.get("/")
async def root():
    return {"message": "HCA API — Hybrid Cognitive Agent"}


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


# ── HCA helpers ───────────────────────────────────────────────────────────────

def _extract_run_summary(run_id: str) -> Dict[str, Any]:
    """Read events and receipts for a run and distil a human-readable summary."""
    from hca.storage import load_run, iter_events, iter_receipts  # type: ignore

    context = load_run(run_id)
    if not context:
        return {}

    events = list(iter_events(run_id))
    receipts = list(iter_receipts(run_id))

    plan: Dict[str, Any] = {}
    action_taken: Dict[str, Any] = {}
    action_result: Dict[str, Any] = {}
    approval_id: Optional[str] = None
    key_events: List[Dict[str, Any]] = []

    for ev in events:
        et = ev.get("event_type", "")
        payload = ev.get("payload", {})

        if et == "module_proposed" and ev.get("actor") == "planner":
            for ci in payload.get("candidate_items", []):
                if ci.get("kind") == "task_plan":
                    c = ci.get("content", {})
                    plan = {
                        "strategy": c.get("strategy"),
                        "action": c.get("action"),
                        "rationale": c.get("rationale", ""),
                        "confidence": ci.get("confidence", 1.0),
                        "memory_context_used": c.get("memory_context_used", False),
                    }

        if et == "action_selected":
            action_taken = {
                "kind": payload.get("kind"),
                "arguments": payload.get("arguments", {}),
                "action_id": payload.get("action_id"),
                "requires_approval": payload.get("requires_approval", False),
            }

        if et == "approval_requested":
            approval_id = payload.get("approval_id")

        if et == "execution_finished":
            action_result = {
                "status": payload.get("status"),
                "outputs": payload.get("outputs"),
                "artifacts": payload.get("artifacts") or [],
                "error": payload.get("error"),
            }

        # Collect key milestones for the trace
        if et in {
            "run_created", "module_proposed", "action_selected",
            "approval_requested", "execution_finished",
            "run_completed", "run_failed", "memory_written",
        }:
            key_events.append({
                "type": et,
                "actor": ev.get("actor"),
                "timestamp": ev.get("timestamp"),
                "summary": _event_summary(et, payload),
            })

    # Memory hits used
    memory_hits: List[Dict[str, Any]] = []
    try:
        from memory_service.singleton import get_controller  # type: ignore
        from memory_service import RetrievalQuery  # type: ignore

        hits = get_controller().retrieve(
            RetrievalQuery(query_text=context.goal, top_k=5, run_id=run_id)
        )
        memory_hits = [
            {
                "text": h.text,
                "score": round(h.score, 3),
                "memory_type": h.memory_type,
                "stored_at": h.stored_at.isoformat() if h.stored_at else None,
            }
            for h in hits
        ]
    except Exception:
        pass

    return {
        "run_id": run_id,
        "goal": context.goal,
        "state": context.state.value,
        "plan": plan,
        "action_taken": action_taken,
        "action_result": action_result,
        "approval_id": approval_id,
        "memory_hits": memory_hits,
        "key_events": key_events[-12:],  # last 12 for the trace
        "event_count": len(events),
    }


def _event_summary(event_type: str, payload: Dict[str, Any]) -> str:
    mapping = {
        "run_created": f"Run started — goal logged",
        "module_proposed": f"Module '{payload.get('source_module', '?')}' proposed {len(payload.get('candidate_items', []))} item(s)",
        "action_selected": f"Selected action: {payload.get('kind', '?')}",
        "approval_requested": f"Approval requested (id={payload.get('approval_id', '?')[:8]}...)",
        "execution_finished": f"Execution {payload.get('status', '?')}",
        "run_completed": "Run completed successfully",
        "run_failed": "Run failed",
        "memory_written": f"Memory written — subject: {payload.get('subject', '?')}",
    }
    return mapping.get(event_type, event_type.replace("_", " "))


# ── HCA endpoints ─────────────────────────────────────────────────────────────

@api_router.post("/hca/run")
async def run_hca(body: HCARunRequest):
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
    return f"event: {event_type}\ndata: {json.dumps(data, default=str)}\n\n"


@api_router.post("/hca/run/stream")
async def stream_hca_run(body: HCARunRequest):
    """Stream HCA pipeline events as Server-Sent Events (SSE).

    Each event payload has the shape:
      { "step": <int>, "event_type": <str>, "label": <str>,
        "actor": <str>, "timestamp": <iso>, "payload": {...} }
    Final 'done' event contains the full run summary.
    """
    result_holder: Dict[str, Any] = {"run_id": None, "done": False, "error": None}

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
                yield _sse("status", {"label": "Pipeline running…", "step": step, "run_id": run_id})
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


@api_router.get("/hca/run/{run_id}")
async def get_hca_run(run_id: str):
    """Fetch current state of an HCA run."""
    from hca.storage import load_run  # type: ignore

    context = load_run(run_id)
    if not context:
        raise HTTPException(status_code=404, detail="Run not found")
    return _extract_run_summary(run_id)


@api_router.post("/hca/run/{run_id}/approve")
async def approve_hca_action(run_id: str, body: HCAApproveRequest):
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
        append_grant(run_id, ApprovalGrant(approval_id=approval_id, token=token))
        rt = Runtime()
        rt._current_state = context.state
        return rt.resume(run_id, approval_id, token)

    new_run_id = await asyncio.to_thread(_approve_and_resume)
    return _extract_run_summary(new_run_id)


@api_router.post("/hca/run/{run_id}/deny")
async def deny_hca_action(run_id: str, body: HCAApproveRequest):
    """Deny a pending HCA action."""
    from hca.runtime.runtime import Runtime  # type: ignore
    from hca.storage import load_run  # type: ignore

    context = load_run(run_id)
    if not context:
        raise HTTPException(status_code=404, detail="Run not found")

    def _deny():
        rt = Runtime()
        rt._current_state = context.state
        return rt.deny_approval(run_id, body.approval_id, reason="Denied by user")

    new_run_id = await asyncio.to_thread(_deny)
    return _extract_run_summary(new_run_id)


@api_router.post("/hca/memory/retrieve")
async def retrieve_memory(body: MemoryQueryRequest):
    """Retrieve memories matching a natural-language query."""
    from memory_service.singleton import get_controller  # type: ignore
    from memory_service import RetrievalQuery  # type: ignore

    hits = get_controller().retrieve(
        RetrievalQuery(query_text=body.query, top_k=body.top_k, run_id=body.run_id)
    )
    return {
        "hits": [
            {
                "text": h.text,
                "score": round(h.score, 3),
                "memory_type": h.memory_type,
                "stored_at": h.stored_at.isoformat() if h.stored_at else None,
                "memory_id": h.memory_id,
            }
            for h in hits
        ]
    }


@api_router.post("/hca/memory/maintain")
async def maintain_memory():
    """Run memory maintenance (TTL expiry)."""
    from memory_service.singleton import get_controller  # type: ignore

    report = get_controller().maintain()
    return report.model_dump()


@api_router.get("/hca/memory/list")
async def list_memory(
    memory_type: Optional[str] = None,
    scope: Optional[str] = None,
    include_expired: bool = False,
    limit: int = 50,
    offset: int = 0,
):
    """List stored memories with optional filtering, newest first."""
    from memory_service.singleton import get_controller  # type: ignore

    records, total = get_controller().list_records(
        memory_type=memory_type,
        scope=scope,
        include_expired=include_expired,
        limit=limit,
        offset=offset,
    )
    return {"records": records, "total": total}


@api_router.delete("/hca/memory/{memory_id}")
async def delete_memory(memory_id: str):
    """Delete a memory record by ID."""
    from memory_service.singleton import get_controller  # type: ignore

    deleted = get_controller().delete_record(memory_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"deleted": True, "memory_id": memory_id}


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


def create_app() -> FastAPI:
    application = FastAPI(title="HCA API")
    application.include_router(api_router)
    application.add_middleware(
        CORSMiddleware,
        allow_credentials=True,
        allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.on_event("startup")
    async def startup_db_client():
        global client, db
        from motor.motor_asyncio import AsyncIOMotorClient

        settings = _load_settings()
        client = AsyncIOMotorClient(settings.mongo_url)
        db = client[settings.db_name]

    @application.on_event("shutdown")
    async def shutdown_db_client():
        global client, db

        if client is not None:
            client.close()
        client = None
        db = None

    return application


app = create_app()
