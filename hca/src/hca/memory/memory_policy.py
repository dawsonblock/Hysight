"""Memory promotion and write policy rules."""

from __future__ import annotations

from typing import Iterable, List, Optional

from hca.common.types import MemoryRecord
from hca.memory.contradiction_check import check_contradictions


_MIN_IDENTITY_CONFIDENCE = 0.9
_MIN_IDENTITY_SUPPORT = 2


def _same_subject(records: Iterable[MemoryRecord]) -> bool:
    records = list(records)
    if not records:
        return False
    subject = records[0].subject
    return bool(subject) and all(
        record.subject == subject for record in records
    )


def can_promote_to_semantic(records: List[MemoryRecord]) -> bool:
    if len(records) < 2 or not _same_subject(records):
        return False
    baseline = records[0]
    return not any(
        check_contradictions(record, [baseline]).has_contradiction
        for record in records[1:]
    )


def can_promote_to_procedural(records: List[MemoryRecord]) -> bool:
    successful = [
        record
        for record in records
        if isinstance(record.content, dict)
        and record.content.get("status") == "success"
        and record.content.get("action_kind")
    ]
    if len(successful) < 2:
        return False
    action_kind = successful[0].content.get("action_kind")
    return all(
        record.content.get("action_kind") == action_kind
        for record in successful
    )


def can_promote_to_identity(
    record: MemoryRecord,
    supporting_records: Optional[List[MemoryRecord]] = None,
) -> bool:
    supporting_records = supporting_records or []
    support_count = len(supporting_records) + max(1, len(record.provenance))
    if not record.subject or record.confidence < _MIN_IDENTITY_CONFIDENCE:
        return False
    if support_count < _MIN_IDENTITY_SUPPORT:
        return False
    contradiction = check_contradictions(record, supporting_records)
    return not contradiction.has_contradiction


def can_write_identity(record: MemoryRecord) -> bool:
    """Determine whether an identity record can be written without approval."""
    return can_promote_to_identity(record)
