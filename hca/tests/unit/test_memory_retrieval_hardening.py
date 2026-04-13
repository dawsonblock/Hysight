from hca.memory.retrieval import retrieve
from hca.memory.episodic_store import EpisodicStore
from hca.common.types import MemoryRecord, MemoryType


def test_retrieval_resilience(monkeypatch, tmp_path):
    monkeypatch.setenv("HCA_STORAGE_ROOT", str(tmp_path / "storage"))

    run_id = "test_resilience_clean"
    store = EpisodicStore(run_id)

    # Add malformed/partial records
    store.append(
        MemoryRecord(
            memory_type=MemoryType.episodic,
            subject=None,
            content="some content",
        )
    )
    store.append(
        MemoryRecord(
            memory_type=MemoryType.episodic,
            subject="some subject",
            content=None,
        )
    )
    store.append(
        MemoryRecord(
            memory_type=MemoryType.episodic,
            subject=None,
            content=None,
        )
    )

    # Should not crash
    results = retrieve(run_id, "some")
    # Record 1 matches "some" in content
    # Record 2 matches "some" in subject
    # Record 3 matches nothing
    assert len(results) == 2

    # Should handle None query
    results = retrieve(run_id, None)
    # If query is None, query_lower is "", which matches everything
    assert len(results) == 3


if __name__ == "__main__":
    raise SystemExit("Run this module with pytest")
