"""
Contract types for the HCA ↔ Memory service boundary.
Matches schema.json exactly. Both the Python implementation and the Rust
service must honour these shapes.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return str(uuid.uuid4())


# ─── inbound ──────────────────────────────────────────────────────────────────

class Provenance(BaseModel):
    source_type: str = "chat"          # chat | file | tool | system | external
    source_id:   str = Field(default_factory=_new_id)
    source_label: Optional[str] = None
    trust_weight: float = 0.5


class CandidateMemory(BaseModel):
    candidate_id: str = Field(default_factory=_new_id)
    raw_text:    str
    memory_type: str = "trace"         # trace | episode | fact | preference | goalstate | procedure
    entity:      str = ""
    slot:        str = ""
    value:       str = ""
    confidence:  float = 0.5
    salience:    float = 0.5
    scope:       str = "private"       # private | task | project | shared
    run_id:      Optional[str] = None
    workflow_key: Optional[str] = None
    source:      Provenance = Field(default_factory=Provenance)
    tags:        List[str] = Field(default_factory=list)
    metadata:    Dict[str, Any] = Field(default_factory=dict)
    # Session isolation — matches sidecar user_id field.
    user_id:     str = "default"
    # Pre-computed embedding (384-dim bge-small-en-v1.5), optional.
    embedding:   Optional[List[float]] = None


class RetrievalQuery(BaseModel):
    query_text:      str
    top_k:           int = 10
    memory_layer:    Optional[str] = None
    scope:           Optional[str] = None
    run_id:          Optional[str] = None
    include_expired: bool = False
    intent:          str = "general"   # general | historical_fact | episodic_recall | belief_check
    # Session isolation.
    user_id:         str = "default"
    # Pre-computed query embedding for semantic/hybrid search.
    embedding:       Optional[List[float]] = None
    # "bm25" | "semantic" | "hybrid"
    mode:            str = "bm25"


# ─── outbound ─────────────────────────────────────────────────────────────────

class RetrievalHit(BaseModel):
    memory_id:    Optional[str] = None
    belief_id:    Optional[str] = None
    memory_layer: str = "trace"
    memory_type:  Optional[str] = None
    entity:       Optional[str] = None
    slot:         Optional[str] = None
    value:        Optional[str] = None
    text:         str
    score:        float = 0.0
    confidence:   float = 0.5
    stored_at:    datetime = Field(default_factory=_utc_now)
    expired:      bool = False
    metadata:     Dict[str, Any] = Field(default_factory=dict)


class MaintenanceReport(BaseModel):
    durable_memory_count: int = 0
    expired_count:        int = 0
    expired_ids:          List[str] = Field(default_factory=list)
    compaction_supported: bool = False
    compactor_status:     str = "unsupported"
