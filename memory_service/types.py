"""
Contract types for the HCA ↔ Memory service boundary.
Matches schema.json exactly. Both the Python implementation and the Rust
service must honour these shapes.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

MemoryType = Literal[
    "trace",
    "episode",
    "fact",
    "preference",
    "goalstate",
    "procedure",
]
ScopeType = Literal["private", "task", "project", "shared"]
IntentType = Literal[
    "general",
    "historical_fact",
    "episodic_recall",
    "belief_check",
]


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return str(uuid.uuid4())


# Inbound.

class Provenance(ContractModel):
    source_type: str = "chat"          # chat | file | tool | system | external
    source_id: str = Field(default_factory=_new_id)
    source_label: Optional[str] = None
    trust_weight: float = Field(default=0.5, ge=0.0, le=1.0)


class CandidateMemory(ContractModel):
    candidate_id: str = Field(default_factory=_new_id)
    raw_text: str = Field(min_length=1)
    memory_type: MemoryType = "trace"
    entity: str = ""
    slot: str = ""
    value: str = ""
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    salience: float = Field(default=0.5, ge=0.0, le=1.0)
    scope: ScopeType = "private"
    run_id: Optional[str] = None
    workflow_key: Optional[str] = None
    source: Provenance = Field(default_factory=Provenance)
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RetrievalQuery(ContractModel):
    query_text: str = Field(min_length=1)
    top_k: int = Field(default=10, ge=1, le=100)
    memory_layer: Optional[str] = None
    scope: Optional[ScopeType] = None
    run_id: Optional[str] = None
    include_expired: bool = False
    intent: IntentType = "general"


# Outbound.

class RetrievalHit(ContractModel):
    memory_id: Optional[str] = None
    belief_id: Optional[str] = None
    memory_layer: str = "trace"
    memory_type: Optional[MemoryType] = None
    entity: Optional[str] = None
    slot: Optional[str] = None
    value: Optional[str] = None
    text: str
    score: float = 0.0
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    stored_at: datetime = Field(default_factory=_utc_now)
    expired: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RetrievalResponse(ContractModel):
    hits: List[RetrievalHit] = Field(default_factory=list)


class IngestResponse(ContractModel):
    memory_id: Optional[str] = None


class MemoryListItem(ContractModel):
    memory_id: str
    memory_layer: str = "trace"
    memory_type: MemoryType
    text: str
    scope: ScopeType = "private"
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    stored_at: datetime = Field(default_factory=_utc_now)
    expired: bool = False
    run_id: Optional[str] = None


class MemoryListResponse(ContractModel):
    records: List[MemoryListItem] = Field(default_factory=list)
    total: int = Field(default=0, ge=0)


class DeleteMemoryResponse(ContractModel):
    deleted: bool
    memory_id: str


class MaintenanceReport(ContractModel):
    durable_memory_count: int = 0
    expired_count: int = 0
    expired_ids: List[str] = Field(default_factory=list)
    compaction_supported: bool = False
    compactor_status: str = "unsupported"


class SidecarHealthResponse(ContractModel):
    status: str
    engine: str
    user_stores: int = Field(ge=0)
