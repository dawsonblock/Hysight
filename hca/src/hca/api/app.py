"""FastAPI application exposing runtime operations."""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException

from hca.api.models import (
    ApprovalActionResponse,
    ApprovalDecisionRequest,
    ApprovalDenyRequest,
    ApprovalGrantRequest,
    ApprovalListResponse,
    ApprovalSummaryItem,
    CreateRunRequest,
    CreateRunResponse,
    HealthResponse,
    MemoryResponse,
    ReplayResponse,
)
from hca.common.enums import MemoryType
from hca.common.types import ApprovalGrant
from hca.memory.episodic_store import EpisodicStore
from hca.memory.identity_store import IdentityStore
from hca.memory.procedural_store import ProceduralStore
from hca.memory.semantic_store import SemanticStore
from hca.runtime.runtime import Runtime
from hca.runtime.replay import reconstruct_state
from hca.storage.approvals import (
    append_grant,
    get_approval_status,
    get_pending_requests,
    iter_records,
)
from hca.storage.event_log import iter_events
from hca.storage.runs import load_run

app = FastAPI(title="Hybrid Cognitive Agent API")
runtime_engine = Runtime()


def _require_run(run_id: str) -> None:
    if load_run(run_id) is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")


def _approval_ids(run_id: str) -> List[str]:
    seen: List[str] = []
    for record in iter_records(run_id):
        approval_id = record.get("approval_id")
        if isinstance(approval_id, str) and approval_id not in seen:
            seen.append(approval_id)
    return seen


def _approval_list(run_id: str) -> ApprovalListResponse:
    items = [
        ApprovalSummaryItem.model_validate(
            get_approval_status(run_id, approval_id)
        )
        for approval_id in _approval_ids(run_id)
    ]
    return ApprovalListResponse(approvals=items)


def _memory_store(memory_type: MemoryType):
    stores = {
        MemoryType.episodic: EpisodicStore,
        MemoryType.semantic: SemanticStore,
        MemoryType.procedural: ProceduralStore,
        MemoryType.identity: IdentityStore,
    }
    return stores[memory_type]


@app.post("/runs", response_model=CreateRunResponse)
def create_run(req: CreateRunRequest) -> CreateRunResponse:
    run_id = runtime_engine.run(req.goal, req.user_id)
    return CreateRunResponse(run_id=run_id)


@app.get("/runs/{run_id}", response_model=ReplayResponse)
def get_run(run_id: str) -> ReplayResponse:
    _require_run(run_id)
    try:
        return ReplayResponse.model_validate(reconstruct_state(run_id))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/runs/{run_id}/state", response_model=ReplayResponse)
def get_run_state(run_id: str) -> ReplayResponse:
    return get_run(run_id)


@app.get("/runs/{run_id}/events", response_model=List[Dict[str, Any]])
def get_events(run_id: str) -> List[Dict[str, Any]]:
    _require_run(run_id)
    return list(iter_events(run_id))


@app.get("/runs/{run_id}/replay", response_model=ReplayResponse)
def get_replay(run_id: str) -> ReplayResponse:
    return get_run(run_id)


@app.get("/runs/{run_id}/approvals", response_model=ApprovalListResponse)
def get_approvals(run_id: str) -> ApprovalListResponse:
    _require_run(run_id)
    return _approval_list(run_id)


@app.get(
    "/runs/{run_id}/approvals/pending",
    response_model=List[Dict[str, Any]],
)
def get_pending_approvals(run_id: str) -> List[Dict[str, Any]]:
    _require_run(run_id)
    return [
        pending.model_dump(mode="json")
        for pending in get_pending_requests(run_id)
    ]


@app.post(
    "/runs/{run_id}/approvals/{approval_id}/grant",
    response_model=ApprovalActionResponse,
)
def grant_approval(
    run_id: str,
    approval_id: str,
    req: ApprovalGrantRequest,
) -> ApprovalActionResponse:
    _require_run(run_id)
    token = req.token or str(uuid.uuid4())
    append_grant(
        run_id,
        ApprovalGrant(
            approval_id=approval_id,
            token=token,
            actor=req.actor or "user",
            expires_at=req.expires_at,
        ),
    )
    try:
        runtime_engine.resume(run_id, approval_id, token)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    replay = reconstruct_state(run_id)
    approval = get_approval_status(run_id, approval_id)
    return ApprovalActionResponse(
        run_id=run_id,
        approval_id=approval_id,
        decision="granted",
        status="granted",
        resolved_status=approval["status"],
        state=replay["state"],
        token=token,
    )


@app.post(
    "/runs/{run_id}/approvals/{approval_id}/deny",
    response_model=ApprovalActionResponse,
)
def deny_approval(
    run_id: str,
    approval_id: str,
    req: Optional[ApprovalDenyRequest] = None,
) -> ApprovalActionResponse:
    _require_run(run_id)
    deny_request = req or ApprovalDenyRequest()
    runtime_engine.deny_approval(
        run_id,
        approval_id,
        reason=deny_request.reason or "User denied via API",
    )
    replay = reconstruct_state(run_id)
    approval = get_approval_status(run_id, approval_id)
    return ApprovalActionResponse(
        run_id=run_id,
        approval_id=approval_id,
        decision="denied",
        status="denied",
        resolved_status=approval["status"],
        state=replay["state"],
        reason=deny_request.reason,
    )


@app.post(
    "/runs/{run_id}/approvals/{approval_id}/decide",
    response_model=ApprovalActionResponse,
)
def decide_approval(
    run_id: str,
    approval_id: str,
    req: ApprovalDecisionRequest,
) -> ApprovalActionResponse:
    if req.decision == "grant":
        return grant_approval(
            run_id,
            approval_id,
            ApprovalGrantRequest(
                token=req.token,
                actor=req.actor,
                expires_at=req.expires_at,
            ),
        )
    if req.decision == "deny":
        return deny_approval(
            run_id,
            approval_id,
            ApprovalDenyRequest(actor=req.actor, reason=req.reason),
        )
    raise HTTPException(status_code=400, detail="Invalid decision")


@app.get(
    "/runs/{run_id}/memory/{memory_type}",
    response_model=MemoryResponse,
)
def get_memory(run_id: str, memory_type: MemoryType) -> MemoryResponse:
    _require_run(run_id)
    store = _memory_store(memory_type)(run_id)
    return MemoryResponse(
        run_id=run_id,
        memory_type=memory_type.value,
        items=[
            record.model_dump(mode="json")
            for record in store.iter_records()
        ],
    )


@app.get("/memory/search")
def search_memory(run_id: str, query: str, limit: int = 5):
    _require_run(run_id)
    from hca.memory.retrieval import retrieve

    results = retrieve(run_id, query, limit)
    return [r.model_dump(mode="json") for r in results]


@app.get("/admin/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")
