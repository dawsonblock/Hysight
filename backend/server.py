import sys
import os

# Add /app to path so memory_service is importable
sys.path.insert(0, "/app")
# Add hca source so `import hca.*` works from the backend
sys.path.insert(0, "/app/hca/src")

# Set HCA working dir so relative storage paths resolve correctly
os.chdir("/app/hca")

from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import Any, Dict, List, Optional
import uuid
import asyncio
import logging
from datetime import datetime, timezone

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

# MongoDB connection
mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

app = FastAPI(title="HCA API")
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
    status_obj = StatusCheck(**input.model_dump())
    doc = status_obj.model_dump()
    doc["timestamp"] = doc["timestamp"].isoformat()
    await db.status_checks.insert_one(doc)
    return status_obj


@api_router.get("/status", response_model=List[StatusCheck])
async def get_status_checks():
    checks = await db.status_checks.find({}, {"_id": 0}).to_list(1000)
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


# ── App assembly ──────────────────────────────────────────────────────────────

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
