"""Compatibility FastAPI application for internal runtime tests."""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException

from hca.api.models import (
    ApprovalActionResponse,
    ApprovalDecisionRequest,
    ApprovalDenyRequest,
    ApprovalGrantRequest,
    CreateRunRequest,
    CreateRunResponse,
    ReplayResponse,
    RunListResponse,
)
from hca.api.runtime_actions import (
    deny_pending_approval,
    grant_pending_approval,
    run_goal,
)
from hca.api.run_views import (
    extract_run_summary,
    list_run_summaries,
    require_pending_approval_selection,
    require_run_context,
)
from hca.storage.approvals import (
    get_approval_status,
    get_pending_requests,
)

app = FastAPI(title="Hybrid Cognitive Agent API")


def _require_run(run_id: str) -> None:
    require_run_context(run_id)


@app.get("/runs", response_model=RunListResponse)
def get_runs(
    query: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
) -> RunListResponse:
    return list_run_summaries(limit=limit, offset=offset, query_text=query)


@app.post("/runs", response_model=CreateRunResponse)
def create_run(req: CreateRunRequest) -> CreateRunResponse:
    run_id = run_goal(req.goal, req.user_id)
    return CreateRunResponse(run_id=run_id)


@app.get("/runs/{run_id}", response_model=ReplayResponse)
def get_run(run_id: str) -> ReplayResponse:
    _require_run(run_id)
    return ReplayResponse.model_validate(
        extract_run_summary(run_id).model_dump(mode="json")
    )


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


def _grant_approval_action(
    run_id: str,
    approval_id: str,
    req: ApprovalGrantRequest,
) -> ApprovalActionResponse:
    require_pending_approval_selection(run_id, approval_id)
    token = req.token or str(uuid.uuid4())
    try:
        grant_pending_approval(
            run_id,
            approval_id,
            token=token,
            actor=req.actor or "user",
            expires_at=req.expires_at,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    replay = extract_run_summary(run_id)
    approval = get_approval_status(run_id, approval_id)
    return ApprovalActionResponse(
        run_id=run_id,
        approval_id=approval_id,
        decision="granted",
        status="granted",
        resolved_status=approval["status"],
        state=replay.state,
        token=token,
    )


def _deny_approval_action(
    run_id: str,
    approval_id: str,
    req: Optional[ApprovalDenyRequest] = None,
) -> ApprovalActionResponse:
    require_pending_approval_selection(run_id, approval_id)
    deny_request = req or ApprovalDenyRequest()
    try:
        deny_pending_approval(
            run_id,
            approval_id,
            reason=deny_request.reason or "User denied via API",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    replay = extract_run_summary(run_id)
    approval = get_approval_status(run_id, approval_id)
    return ApprovalActionResponse(
        run_id=run_id,
        approval_id=approval_id,
        decision="denied",
        status="denied",
        resolved_status=approval["status"],
        state=replay.state,
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
        return _grant_approval_action(
            run_id,
            approval_id,
            ApprovalGrantRequest(
                token=req.token,
                actor=req.actor,
                expires_at=req.expires_at,
            ),
        )
    if req.decision == "deny":
        return _deny_approval_action(
            run_id,
            approval_id,
            ApprovalDenyRequest(actor=req.actor, reason=req.reason),
        )
    raise HTTPException(status_code=400, detail="Invalid decision")
