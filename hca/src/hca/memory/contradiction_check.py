"""Logic for detecting contradictions between memory records."""

from __future__ import annotations

from typing import Any, List, Optional

from hca.common.types import ContradictionResult, MemoryRecord


def _dict_conflict_reason(
    subject: str,
    new_content: dict[str, Any],
    existing_content: dict[str, Any],
) -> Optional[str]:
    shared_keys = sorted(set(new_content) & set(existing_content))
    for key in shared_keys:
        if new_content[key] != existing_content[key]:
            return (
                f"Conflicting value for subject '{subject}' key '{key}': "
                f"{new_content[key]!r} vs {existing_content[key]!r}"
            )
    return None


def _content_conflict_reason(
    subject: str,
    new_content: Any,
    existing_content: Any,
) -> Optional[str]:
    if isinstance(new_content, dict) and isinstance(existing_content, dict):
        return _dict_conflict_reason(subject, new_content, existing_content)
    if new_content != existing_content:
        return (
            f"Different content for subject '{subject}': "
            f"{new_content!r} vs {existing_content!r}"
        )
    return None


def check_contradictions(
    new_record: MemoryRecord,
    existing_records: List[MemoryRecord],
) -> ContradictionResult:
    """Check for contradictions between a new record and existing memories."""
    subject = new_record.subject
    if not subject:
        return ContradictionResult(has_contradiction=False)

    conflicting_record_ids: List[str] = []
    reason: Optional[str] = None
    for existing in existing_records:
        if existing.subject != subject:
            continue
        conflict_reason = _content_conflict_reason(
            subject,
            new_record.content,
            existing.content,
        )
        if conflict_reason:
            conflicting_record_ids.append(existing.record_id)
            reason = reason or conflict_reason

    return ContradictionResult(
        has_contradiction=bool(conflicting_record_ids),
        reason=reason,
        subject=subject,
        conflicting_record_ids=conflicting_record_ids,
    )


def detect_contradictions(
    existing_records: List[MemoryRecord], new_record: MemoryRecord
) -> bool:
    """Return True if the new record contradicts any existing record."""
    return check_contradictions(new_record, existing_records).has_contradiction
