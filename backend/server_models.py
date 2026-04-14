import uuid
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


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


class DatabaseSubsystemStatus(BackendModel):
    enabled: bool
    status: str
    detail: str


class MemorySubsystemStatus(BackendModel):
    backend: str
    uses_sidecar: bool
    status: str
    detail: str
    service_url: Optional[str] = None


class StorageSubsystemStatus(BackendModel):
    status: str
    detail: str
    root: str
    memory_dir: str


class LLMSubsystemStatus(BackendModel):
    status: str
    detail: str


class SubsystemsResponse(BackendModel):
    status: str
    database: DatabaseSubsystemStatus
    memory: MemorySubsystemStatus
    storage: StorageSubsystemStatus
    llm: LLMSubsystemStatus