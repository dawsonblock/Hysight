from datetime import timedelta

from hca.common.types import MemoryRecord
from hca.common.enums import MemoryType
from hca.common.time import utc_now
from hca.memory.retrieval import retrieve, calculate_staleness
from hca.memory.contradiction_check import check_contradictions
from hca.memory.episodic_store import EpisodicStore


def test_staleness_logic():
    now = utc_now()
    old_time = now - timedelta(days=15)
    rec = MemoryRecord(
        run_id="test_memory_v5",
        memory_type=MemoryType.episodic,
        subject="test",
        content="old news",
        created_at=old_time,
        updated_at=old_time
    )
    staleness = calculate_staleness(rec)
    assert 0.4 < staleness < 0.6


def test_contradiction_detection():
    r1 = MemoryRecord(
        run_id="test_memory_v5",
        memory_type=MemoryType.episodic,
        subject="color",
        content={"key": "sky", "value": "blue"}
    )
    r2 = MemoryRecord(
        run_id="test_memory_v5",
        memory_type=MemoryType.episodic,
        subject="color",
        content={"key": "sky", "value": "red"}
    )

    contradictions = check_contradictions(r2, [r1])
    assert contradictions.has_contradiction is True
    assert "red" in (contradictions.reason or "")
    assert "blue" in (contradictions.reason or "")


def test_retrieval_integration(monkeypatch, tmp_path):
    monkeypatch.setenv("HCA_STORAGE_ROOT", str(tmp_path / "storage"))

    run_id = "test_memory_v5"
    store = EpisodicStore(run_id)

    # Write two records for same subject but different content
    store.append(MemoryRecord(
        run_id=run_id,
        memory_type=MemoryType.episodic,
        subject="status",
        content="online",
        confidence=0.9
    ))
    store.append(MemoryRecord(
        run_id=run_id,
        memory_type=MemoryType.episodic,
        subject="status",
        content="offline",
        confidence=0.8
    ))

    results = retrieve(run_id, "status")
    assert len(results) == 2
    # Both should be marked as contradictory
    assert results[0].contradiction is True
    assert results[1].contradiction is True
    # Sorted by confidence
    assert results[0].record.content == "online"


if __name__ == "__main__":
    raise SystemExit("Run this module with pytest")
