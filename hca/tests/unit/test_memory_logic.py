from datetime import datetime, timezone, timedelta
from hca.memory.retrieval import retrieve
from hca.memory.identity_store import IdentityStore
from hca.common.types import MemoryRecord, MemoryType


def test_memory_contradiction():
    import uuid
    run_id = f"test_contradiction_{uuid.uuid4()}"
    store = IdentityStore(run_id)

    # Add two records for the same subject with different content
    store.append(MemoryRecord(
        memory_type=MemoryType.identity,
        subject="user_name",
        content="Alice",
        confidence=1.0
    ))
    store.append(MemoryRecord(
        memory_type=MemoryType.identity,
        subject="user_name",
        content="Bob",
        confidence=0.8
    ))

    results = retrieve(run_id, "user_name")
    assert len(results) == 2
    # Both should be marked as contradictory
    assert results[0].contradiction is True
    assert results[1].contradiction is True


def test_memory_staleness():
    import uuid
    run_id = f"test_staleness_{uuid.uuid4()}"
    store = IdentityStore(run_id)

    # Record from 10 days ago
    old_time = datetime.now(timezone.utc) - timedelta(days=10)
    old_record = MemoryRecord(
        memory_type=MemoryType.identity,
        subject="status",
        content="old",
        updated_at=old_time
    )
    store.append(old_record)

    results = retrieve(run_id, "status")

    assert results[0].staleness > 0.3


if __name__ == "__main__":
    test_memory_contradiction()
    print("test_memory_contradiction passed")
    test_memory_staleness()
    print("test_memory_staleness passed")
