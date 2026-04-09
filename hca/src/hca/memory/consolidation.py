"""Memory consolidation logic for bounded promotion candidates."""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

from hca.common.enums import MemoryType
from hca.common.types import MemoryRecord, PromotionCandidate
from hca.memory.episodic_store import EpisodicStore
from hca.memory.memory_policy import (
    can_promote_to_procedural,
    can_promote_to_semantic,
)
from hca.memory.semantic_store import SemanticStore


def _average_confidence(records: List[MemoryRecord]) -> float:
    if not records:
        return 0.0
    return sum(record.confidence for record in records) / len(records)


def consolidate_episodic(
    run_id: str,
    count_threshold: int = 3,
    auto_write: bool = False,
) -> List[PromotionCandidate]:
    """Generate bounded promotion candidates from episodic memory."""
    episodic = EpisodicStore(run_id)
    semantic = SemanticStore(run_id)

    by_subject: Dict[str, List[MemoryRecord]] = defaultdict(list)
    for rec in episodic.iter_records():
        if rec.subject:
            by_subject[rec.subject].append(rec)

    candidates: List[PromotionCandidate] = []
    for subject, records in sorted(by_subject.items()):
        if len(records) < count_threshold:
            continue

        latest = max(records, key=lambda record: record.created_at)
        support_ids = [record.record_id for record in records]
        if can_promote_to_semantic(records):
            candidate = PromotionCandidate(
                candidate_type=MemoryType.semantic,
                subject=subject,
                content=latest.content,
                supporting_record_ids=support_ids,
                confidence=_average_confidence(records),
                support_count=len(records),
                contradiction_free=True,
            )
            candidates.append(candidate)
            if auto_write:
                semantic.write(
                    MemoryRecord(
                        run_id=run_id,
                        memory_type=MemoryType.semantic,
                        subject=subject,
                        content=latest.content,
                        confidence=candidate.confidence,
                        provenance=support_ids,
                    )
                )

        if can_promote_to_procedural(records):
            action_record = next(
                record
                for record in records
                if isinstance(record.content, dict)
                and record.content.get("action_kind")
            )
            candidates.append(
                PromotionCandidate(
                    candidate_type=MemoryType.procedural,
                    subject=action_record.content.get("action_kind"),
                    content=action_record.content,
                    supporting_record_ids=support_ids,
                    confidence=_average_confidence(records),
                    support_count=len(records),
                    contradiction_free=True,
                )
            )

    return candidates


def propose_consolidation(
    record: MemoryRecord,
) -> PromotionCandidate | None:
    """Produce a semantic promotion candidate for a single strong record."""
    if not record.subject:
        return None
    return PromotionCandidate(
        candidate_type=MemoryType.semantic,
        subject=record.subject,
        content=record.content,
        supporting_record_ids=[record.record_id],
        confidence=record.confidence,
        support_count=max(1, len(record.provenance)),
        contradiction_free=not record.contradiction_status,
    )
