"""Structured memory retrieval with contradiction and staleness metadata."""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Optional

from hca.common.enums import MemoryType
from hca.common.types import MemoryRecord, RetrievalItem
from hca.common.time import utc_now
from hca.memory.contradiction_check import check_contradictions
from hca.memory.episodic_store import EpisodicStore
from hca.memory.identity_store import IdentityStore
from hca.memory.procedural_store import ProceduralStore
from hca.memory.semantic_store import SemanticStore


_STORE_TYPES = {
    MemoryType.episodic: EpisodicStore,
    MemoryType.semantic: SemanticStore,
    MemoryType.procedural: ProceduralStore,
    MemoryType.identity: IdentityStore,
}


def calculate_staleness(record: MemoryRecord) -> float:
    """Calculate staleness score (0.0 fresh to 1.0 very stale)."""
    now = utc_now()
    ref_time = record.updated_at or record.created_at

    if ref_time.tzinfo is None:
        from datetime import timezone

        ref_time = ref_time.replace(tzinfo=timezone.utc)

    age = now - ref_time
    age_days = age.total_seconds() / (24 * 3600)
    return min(1.0, age_days / 30.0)


def _selected_store_types(
    memory_types: Optional[List[MemoryType | str]] = None,
) -> List[MemoryType]:
    if not memory_types:
        return list(_STORE_TYPES)
    selected: List[MemoryType] = []
    for memory_type in memory_types:
        selected.append(
            memory_type
            if isinstance(memory_type, MemoryType)
            else MemoryType(memory_type)
        )
    return selected


def _matches_query(
    record: MemoryRecord,
    query: Optional[str],
    subject_exact: Optional[str],
) -> bool:
    if subject_exact is not None and record.subject != subject_exact:
        return False
    if query is None:
        return True
    query_lower = query.lower()
    subject = (record.subject or "").lower()
    content = str(record.content or "").lower()
    return query_lower in subject or query_lower in content


def _mark_contradictions(items: List[RetrievalItem]) -> List[RetrievalItem]:
    by_subject: Dict[str, List[RetrievalItem]] = defaultdict(list)
    for item in items:
        subject = item.record.subject
        if subject:
            by_subject[subject].append(item)

    for subject_items in by_subject.values():
        if len(subject_items) < 2:
            continue
        for index, item in enumerate(subject_items):
            other_records = [
                other.record
                for other_index, other in enumerate(subject_items)
                if other_index != index
            ]
            contradiction = check_contradictions(item.record, other_records)
            item.contradiction = contradiction.has_contradiction
            item.record.contradiction_status = contradiction.has_contradiction
    return items


def retrieve(
    run_id: str,
    query: Optional[str] = None,
    limit: int = 5,
    memory_types: Optional[List[MemoryType | str]] = None,
    max_staleness: Optional[float] = None,
    subject_exact: Optional[str] = None,
    text_query: Optional[str] = None,
) -> List[RetrievalItem]:
    """Retrieve memories with explicit metadata and bounded filtering."""
    effective_query = text_query if text_query is not None else query
    results: List[RetrievalItem] = []

    for memory_type in _selected_store_types(memory_types):
        store = _STORE_TYPES[memory_type](run_id)
        for record in store.iter_records():
            staleness = calculate_staleness(record)
            if max_staleness is not None and staleness > max_staleness:
                continue
            if not _matches_query(record, effective_query, subject_exact):
                continue
            copied_record = record.model_copy(deep=True)
            results.append(
                RetrievalItem(
                    record=copied_record,
                    confidence=copied_record.confidence,
                    staleness=staleness,
                    contradiction=False,
                    provenance=list(copied_record.provenance),
                    memory_type=copied_record.memory_type,
                )
            )

    _mark_contradictions(results)
    results.sort(
        key=lambda item: (
            item.contradiction,
            -item.confidence,
            item.staleness,
            item.record.subject or "",
            item.record.record_id,
        )
    )
    return results[:limit]


def retrieve_all(run_id: str, subject: str) -> List[RetrievalItem]:
    """Retrieve records across all memory stores by exact subject."""
    return retrieve(
        run_id,
        limit=10_000,
        subject_exact=subject,
        text_query=None,
    )
