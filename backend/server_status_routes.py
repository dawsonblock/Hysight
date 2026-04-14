from datetime import datetime
from typing import Any, Awaitable, Callable, List

from fastapi import APIRouter

from backend.server_models import (
    APIRootResponse,
    StatusCheck,
    StatusCheckCreate,
    SubsystemsResponse,
)


def register_status_routes(
    router: APIRouter,
    *,
    require_db: Callable[[], Any],
    get_subsystems: Callable[[], Awaitable[SubsystemsResponse]],
) -> None:
    @router.get("/", response_model=APIRootResponse)
    async def root():
        return APIRootResponse(message="HCA API — Hybrid Cognitive Agent")

    @router.post("/status", response_model=StatusCheck)
    async def create_status_check(input: StatusCheckCreate):
        database = require_db()
        status_obj = StatusCheck(**input.model_dump())
        doc = status_obj.model_dump()
        doc["timestamp"] = doc["timestamp"].isoformat()
        await database.status_checks.insert_one(doc)
        return status_obj

    @router.get("/status", response_model=List[StatusCheck])
    async def get_status_checks():
        database = require_db()
        checks = await database.status_checks.find({}, {"_id": 0}).to_list(1000)
        for check in checks:
            if isinstance(check.get("timestamp"), str):
                check["timestamp"] = datetime.fromisoformat(check["timestamp"])
        return checks

    @router.get("/subsystems", response_model=SubsystemsResponse)
    async def get_subsystem_status():
        return await get_subsystems()