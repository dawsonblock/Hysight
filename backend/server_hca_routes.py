import asyncio
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from backend import server_bootstrap as _server_bootstrap  # noqa: F401
from backend.server_streaming import stream_hca_run
from hca.api.models import (  # type: ignore[import-untyped]
    ApprovalSelectionRequest,
    CreateRunRequest,
    RunArtifactDetailResponse as HCARunArtifactDetailResponse,
    RunArtifactListResponse as HCARunArtifactListResponse,
    RunEventListResponse as HCARunEventListResponse,
    RunListResponse as HCARunListResponse,
    RunSummaryResponse as HCARunSummaryResponse,
)
from hca.api.runtime_actions import (  # noqa: E402
    deny_pending_approval,
    grant_pending_approval,
    run_goal,
)
from hca.api.run_views import (  # noqa: E402
    extract_run_summary,
    get_run_artifact_detail,
    list_run_artifacts,
    list_run_events,
    list_run_summaries,
    require_pending_approval_selection,
    require_run_context,
)


def register_hca_routes(router: APIRouter) -> None:
    @router.get("/hca/runs", response_model=HCARunListResponse)
    async def list_hca_runs(
        q: Optional[str] = Query(default=None, max_length=200),
        limit: int = Query(default=20, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
    ):
        return list_run_summaries(limit=limit, offset=offset, query_text=q)

    @router.post("/hca/run", response_model=HCARunSummaryResponse)
    async def run_hca(body: CreateRunRequest):
        def _execute():
            return run_goal(body.goal, user_id=body.user_id)

        run_id = await asyncio.to_thread(_execute)
        return extract_run_summary(run_id)

    @router.post("/hca/run/stream")
    async def stream_hca(body: CreateRunRequest):
        return await stream_hca_run(body, extract_run_summary)

    @router.get("/hca/run/{run_id}", response_model=HCARunSummaryResponse)
    async def get_hca_run(run_id: str):
        require_run_context(run_id)
        return extract_run_summary(run_id)

    @router.get(
        "/hca/run/{run_id}/events",
        response_model=HCARunEventListResponse,
    )
    async def list_hca_run_events(
        run_id: str,
        limit: int = Query(default=100, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
    ):
        return list_run_events(run_id, limit=limit, offset=offset)

    @router.get(
        "/hca/run/{run_id}/artifacts",
        response_model=HCARunArtifactListResponse,
    )
    async def list_hca_run_artifacts(
        run_id: str,
        limit: int = Query(default=100, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
    ):
        return list_run_artifacts(run_id, limit=limit, offset=offset)

    @router.get(
        "/hca/run/{run_id}/artifacts/{artifact_id}",
        response_model=HCARunArtifactDetailResponse,
    )
    async def get_hca_run_artifact(
        run_id: str,
        artifact_id: str,
        preview_bytes: int = Query(default=20000, ge=1, le=200000),
    ):
        return get_run_artifact_detail(
            run_id,
            artifact_id,
            preview_bytes=preview_bytes,
        )

    @router.post(
        "/hca/run/{run_id}/approve",
        response_model=HCARunSummaryResponse,
    )
    async def approve_hca_action(
        run_id: str,
        body: ApprovalSelectionRequest,
    ):
        token = str(uuid.uuid4())
        approval_id = body.approval_id
        require_pending_approval_selection(run_id, approval_id)

        def _approve_and_resume():
            return grant_pending_approval(
                run_id,
                approval_id,
                token=token,
                actor="user",
            )

        try:
            new_run_id = await asyncio.to_thread(_approve_and_resume)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return extract_run_summary(new_run_id)

    @router.post(
        "/hca/run/{run_id}/deny",
        response_model=HCARunSummaryResponse,
    )
    async def deny_hca_action(
        run_id: str,
        body: ApprovalSelectionRequest,
    ):
        require_pending_approval_selection(run_id, body.approval_id)

        def _deny():
            return deny_pending_approval(
                run_id,
                body.approval_id,
                reason="Denied by user",
            )

        try:
            new_run_id = await asyncio.to_thread(_deny)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return extract_run_summary(new_run_id)