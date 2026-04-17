"""Memory API tests — list, filter, pagination, delete, 404.

All tests are self-contained: data is seeded directly via the MemoryController
singleton (which is isolated to a tmp directory by the app_client fixture in
conftest.py). No external service or pre-existing state is required.
"""
from datetime import datetime, timedelta, timezone
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _seed(text, memory_type="fact", scope="shared"):
    from memory_service.singleton import get_controller
    from memory_service import CandidateMemory

    return get_controller().ingest(
        CandidateMemory(raw_text=text, memory_type=memory_type, scope=scope)
    )


# List.


def test_list_returns_records(app_client):
    _seed("alpha record")
    _seed("beta record")
    r = app_client.get("/api/hca/memory/list")
    assert r.status_code == 200
    data = r.json()
    assert "records" in data
    assert "total" in data
    assert data["total"] == 2
    assert len(data["records"]) == 2
    assert isinstance(data["records"][0]["text"], str)


def test_list_filter_by_type_episode(app_client):
    _seed("some episode", memory_type="episode")
    _seed("some fact", memory_type="fact")
    r = app_client.get("/api/hca/memory/list?memory_type=episode")
    assert r.status_code == 200
    data = r.json()
    assert len(data["records"]) == 1
    assert data["records"][0]["memory_type"] == "episode"


def test_list_pagination(app_client):
    for i in range(3):
        _seed(f"record {i}")
    r = app_client.get("/api/hca/memory/list?limit=2&offset=0")
    assert r.status_code == 200
    data = r.json()
    assert len(data["records"]) == 2
    assert data["total"] == 3


def test_record_fields(app_client):
    _seed("field check record")
    r = app_client.get("/api/hca/memory/list?limit=1")
    assert r.status_code == 200
    rec = r.json()["records"][0]
    expected_keys = {
        "memory_id",
        "memory_layer",
        "memory_type",
        "text",
        "scope",
        "confidence",
        "stored_at",
        "expired",
        "run_id",
    }
    assert expected_keys.issubset(rec.keys())
    assert isinstance(rec["memory_id"], str)
    assert isinstance(rec["memory_type"], str)
    assert isinstance(rec["text"], str)
    assert rec["memory_layer"] == "trace"
    assert "scope" in rec
    assert "raw_text" not in rec
    assert "stored_at" in rec
    assert "expired" in rec
    assert rec["expired"] is False


def test_list_invalid_limit_returns_422(app_client):
    r = app_client.get("/api/hca/memory/list?limit=0")
    assert r.status_code == 422


def test_list_invalid_scope_returns_422(app_client):
    r = app_client.get("/api/hca/memory/list?scope=invalid")
    assert r.status_code == 422


# Delete.


def test_delete_nonexistent_returns_404(app_client):
    r = app_client.delete("/api/hca/memory/nonexistent-id")
    assert r.status_code == 404


def test_delete_removes_record(app_client):
    _seed("to be deleted")

    # Confirm it's there
    list_r = app_client.get("/api/hca/memory/list")
    assert list_r.status_code == 200
    records = list_r.json()["records"]
    assert len(records) == 1
    mem_id = records[0]["memory_id"]

    # Delete
    del_r = app_client.delete(f"/api/hca/memory/{mem_id}")
    assert del_r.status_code == 200
    data = del_r.json()
    assert data == {"deleted": True, "memory_id": mem_id}

    # Verify gone
    r2 = app_client.get("/api/hca/memory/list")
    assert r2.json()["total"] == 0


def test_controller_reload_ignores_truncated_final_record(
    monkeypatch,
    tmp_path,
):
    from memory_service import CandidateMemory
    from memory_service.controller import MemoryController

    storage_root = tmp_path / "storage"
    memory_dir = storage_root / "memory"
    monkeypatch.setenv("MEMORY_BACKEND", "python")
    monkeypatch.delenv("MEMORY_SERVICE_URL", raising=False)
    monkeypatch.setenv("HCA_STORAGE_ROOT", str(storage_root))
    monkeypatch.setenv("MEMORY_STORAGE_DIR", str(memory_dir))

    controller = MemoryController(storage_dir=str(memory_dir))
    memory_id = controller.ingest(CandidateMemory(raw_text="alpha record"))

    with open(memory_dir / "memories.jsonl", "ab") as handle:
        handle.write(b'{"memory_id":"truncated"')

    reloaded = MemoryController(storage_dir=str(memory_dir))
    records, total = reloaded.list_records()

    assert total == 1
    assert [record.memory_id for record in records] == [memory_id]


def test_controller_retrieve_prefers_newest_on_tied_scores(
    monkeypatch,
    tmp_path,
):
    from memory_service import CandidateMemory, RetrievalQuery
    from memory_service.controller import MemoryController

    storage_root = tmp_path / "storage"
    memory_dir = storage_root / "memory"
    monkeypatch.setenv("MEMORY_BACKEND", "python")
    monkeypatch.delenv("MEMORY_SERVICE_URL", raising=False)
    monkeypatch.setenv("HCA_STORAGE_ROOT", str(storage_root))
    monkeypatch.setenv("MEMORY_STORAGE_DIR", str(memory_dir))

    controller = MemoryController(storage_dir=str(memory_dir))
    controller.ingest(
        CandidateMemory(
            raw_text="alpha beta",
            metadata={"ordinal": "first"},
        )
    )
    controller.ingest(
        CandidateMemory(
            raw_text="alpha beta",
            metadata={"ordinal": "second"},
        )
    )

    hits = controller.retrieve(
        RetrievalQuery(query_text="alpha beta", top_k=2)
    )

    assert [hit.metadata["ordinal"] for hit in hits] == [
        "second",
        "first",
    ]


def test_controller_ingest_rolls_back_on_disk_failure(
    monkeypatch,
    tmp_path,
):
    from memory_service import CandidateMemory
    from memory_service.controller import MemoryController

    storage_root = tmp_path / "storage"
    memory_dir = storage_root / "memory"
    monkeypatch.setenv("MEMORY_BACKEND", "python")
    monkeypatch.delenv("MEMORY_SERVICE_URL", raising=False)
    monkeypatch.setenv("HCA_STORAGE_ROOT", str(storage_root))
    monkeypatch.setenv("MEMORY_STORAGE_DIR", str(memory_dir))

    controller = MemoryController(storage_dir=str(memory_dir))

    def _explode(_record):
        raise OSError("disk full")

    monkeypatch.setattr(controller, "_append_to_disk", _explode)

    with pytest.raises(OSError, match="disk full"):
        controller.ingest(CandidateMemory(raw_text="alpha record"))

    records, total = controller.list_records(include_expired=True)

    assert total == 0
    assert records == []


def test_controller_maintain_persists_expired_records_on_reload(
    monkeypatch,
    tmp_path,
):
    from memory_service import CandidateMemory
    from memory_service.controller import MemoryController

    storage_root = tmp_path / "storage"
    memory_dir = storage_root / "memory"
    monkeypatch.setenv("MEMORY_BACKEND", "python")
    monkeypatch.delenv("MEMORY_SERVICE_URL", raising=False)
    monkeypatch.setenv("HCA_STORAGE_ROOT", str(storage_root))
    monkeypatch.setenv("MEMORY_STORAGE_DIR", str(memory_dir))

    controller = MemoryController(storage_dir=str(memory_dir))
    memory_id = controller.ingest(
        CandidateMemory(raw_text="stale fact", memory_type="fact")
    )
    controller._records[0]["stored_at"] = (
        datetime.now(timezone.utc) - timedelta(days=8)
    ).isoformat()
    controller._rewrite_disk()

    report = controller.maintain()
    reloaded = MemoryController(storage_dir=str(memory_dir))
    records, total = reloaded.list_records(include_expired=True)

    assert report.expired_ids == [memory_id]
    assert total == 1
    assert records[0].memory_id == memory_id
    assert records[0].expired is True
