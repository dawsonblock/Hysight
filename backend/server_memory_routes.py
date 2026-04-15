from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from backend import server_bootstrap as _server_bootstrap  # noqa: F401
from memory_service import (  # noqa: E402
    DeleteMemoryResponse,
    MaintenanceReport,
    MemoryConfigurationError,
    MemoryListResponse,
    RetrievalQuery,
    RetrievalResponse,
)
from memory_service.controller import MemoryBackendError  # noqa: E402
from memory_service.types import MemoryType, ScopeType  # noqa: E402


def _memory_route_unavailable_detail(exc: Exception) -> str:
    detail = str(exc).strip()
    if "/api/subsystems" in detail:
        return detail.rstrip(".") + "."
    return (
        f"Active memory authority is unavailable: {detail.rstrip('.')}. "
        "Check /api/subsystems for the authoritative memory, sidecar, and "
        "optional Mongo status."
    )


def register_memory_routes(router: APIRouter) -> None:
    @router.post("/hca/memory/retrieve", response_model=RetrievalResponse)
    async def retrieve_memory(body: RetrievalQuery):
        from memory_service.singleton import get_controller  # type: ignore

        try:
            return RetrievalResponse(hits=get_controller().retrieve(body))
        except (MemoryBackendError, MemoryConfigurationError) as exc:
            raise HTTPException(
                status_code=503,
                detail=_memory_route_unavailable_detail(exc),
            ) from exc

    @router.post("/hca/memory/maintain", response_model=MaintenanceReport)
    async def maintain_memory():
        from memory_service.singleton import get_controller  # type: ignore

        try:
            return get_controller().maintain()
        except (MemoryBackendError, MemoryConfigurationError) as exc:
            raise HTTPException(
                status_code=503,
                detail=_memory_route_unavailable_detail(exc),
            ) from exc

    @router.get("/hca/memory/list", response_model=MemoryListResponse)
    async def list_memory(
        memory_type: Optional[MemoryType] = None,
        scope: Optional[ScopeType] = None,
        include_expired: bool = False,
        limit: int = Query(default=50, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
    ):
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
            raise HTTPException(
                status_code=503,
                detail=_memory_route_unavailable_detail(exc),
            ) from exc
        return MemoryListResponse(records=records, total=total)

    @router.delete(
        "/hca/memory/{memory_id}",
        response_model=DeleteMemoryResponse,
    )
    async def delete_memory(memory_id: str):
        from memory_service.singleton import get_controller  # type: ignore

        try:
            deleted = get_controller().delete_record(memory_id)
        except (MemoryBackendError, MemoryConfigurationError) as exc:
            raise HTTPException(
                status_code=503,
                detail=_memory_route_unavailable_detail(exc),
            ) from exc
        if not deleted:
            raise HTTPException(status_code=404, detail="Memory not found")
        return DeleteMemoryResponse(deleted=True, memory_id=memory_id)