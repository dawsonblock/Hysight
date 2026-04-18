"""Bounded stress probes for backend runs, memory, and streaming.

These tests intentionally stay small and deterministic. They are designed to
flush out race conditions and corrupted local state without broadening the
default proof surface.
"""

from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from memory_service import CandidateMemory
from memory_service.controller import MemoryController


pytestmark = pytest.mark.integration


def _parse_sse_events(body: str):
    events = []
    event_name = None
    data_lines = []

    for line in body.splitlines():
        if line.startswith("event: "):
            event_name = line.split(": ", 1)[1]
        elif line.startswith("data: "):
            data_lines.append(line.split(": ", 1)[1])
        elif not line.strip() and event_name is not None:
            payload = json.loads("\n".join(data_lines)) if data_lines else None
            events.append((event_name, payload))
            event_name = None
            data_lines = []

    if event_name is not None:
        payload = json.loads("\n".join(data_lines)) if data_lines else None
        events.append((event_name, payload))

    return events


def _local_controller(tmp_path, monkeypatch) -> MemoryController:
    storage_root = tmp_path / "storage"
    memory_dir = storage_root / "memory"
    monkeypatch.setenv("MEMORY_BACKEND", "python")
    monkeypatch.delenv("MEMORY_SERVICE_URL", raising=False)
    monkeypatch.setenv("HCA_STORAGE_ROOT", str(storage_root))
    monkeypatch.setenv("MEMORY_STORAGE_DIR", str(memory_dir))
    return MemoryController(storage_dir=str(memory_dir))


def test_parallel_backend_runs_keep_event_logs_isolated(app_client):
    goals = [
        f"Parallel backend isolation goal {index}"
        for index in range(6)
    ]

    def _create_run(goal: str) -> tuple[str, str]:
        response = app_client.post("/api/hca/run", json={"goal": goal})
        assert response.status_code == 200
        payload = response.json()
        return payload["run_id"], goal

    with ThreadPoolExecutor(max_workers=4) as executor:
        run_results = list(executor.map(_create_run, goals))

    run_ids = [run_id for run_id, _goal in run_results]
    assert len(set(run_ids)) == len(run_ids)

    for run_id, goal in run_results:
        detail_response = app_client.get(f"/api/hca/run/{run_id}")
        assert detail_response.status_code == 200
        detail = detail_response.json()
        assert detail["run_id"] == run_id
        assert detail["goal"] == goal

        events_response = app_client.get(f"/api/hca/run/{run_id}/events?limit=50")
        assert events_response.status_code == 200
        records = events_response.json()["records"]
        assert records
        assert all(record["run_id"] == run_id for record in records)
        created_goals = [
            record.get("payload", {}).get("goal")
            for record in records
            if record.get("event_type") == "run_created"
        ]
        assert created_goals == [goal]


def test_memory_controller_concurrent_ingest_delete_and_maintain_reloads_cleanly(
    monkeypatch,
    tmp_path,
):
    controller = _local_controller(tmp_path, monkeypatch)

    def _ingest(index: int) -> str:
        return controller.ingest(
            CandidateMemory(
                raw_text=f"stress memory {index}",
                memory_type="fact",
                scope="shared",
            )
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        memory_ids = list(executor.map(_ingest, range(30)))

    with controller._records_lock:
        for record in controller._records[:5]:
            record["stored_at"] = (
                datetime.now(timezone.utc) - timedelta(days=8)
            ).isoformat()
        controller._rewrite_disk()

    to_delete = set(memory_ids[10:20])

    def _delete(memory_id: str) -> bool:
        return controller.delete_record(memory_id)

    def _list_total() -> int:
        _records, total = controller.list_records(include_expired=True)
        return total

    def _maintain_count() -> int:
        return controller.maintain().expired_count

    with ThreadPoolExecutor(max_workers=8) as executor:
        delete_futures = [
            executor.submit(_delete, memory_id)
            for memory_id in sorted(to_delete)
        ]
        list_futures = [
            executor.submit(_list_total)
            for _ in range(10)
        ]
        maintain_futures = [
            executor.submit(_maintain_count)
            for _ in range(5)
        ]

        delete_results = [future.result() for future in delete_futures]
        list_totals = [future.result() for future in list_futures]
        expired_counts = [future.result() for future in maintain_futures]

    assert all(delete_results)
    assert all(total >= 20 for total in list_totals)
    assert all(count >= 5 for count in expired_counts)

    reloaded = _local_controller(tmp_path, monkeypatch)
    records, total = reloaded.list_records(include_expired=True, limit=100, offset=0)
    remaining_ids = {record.memory_id for record in records}

    assert total == 20
    assert remaining_ids.isdisjoint(to_delete)
    assert len(remaining_ids) == total
    assert sum(1 for record in records if record.expired) >= 5


def test_parallel_stream_requests_complete_without_reordering_steps(app_client):
    goals = [
        f"Parallel stream goal {index}"
        for index in range(3)
    ]

    def _run_stream(goal: str):
        response = app_client.post("/api/hca/run/stream", json={"goal": goal})
        assert response.status_code == 200
        events = _parse_sse_events(response.text)
        assert events[0][0] == "status"
        step_payloads = [
            payload
            for name, payload in events
            if name == "step" and isinstance(payload, dict)
        ]
        steps = [payload["step"] for payload in step_payloads]
        assert steps == sorted(steps)
        assert len(steps) == len(set(steps))
        assert any(name == "done" for name, _payload in events)
        return events

    with ThreadPoolExecutor(max_workers=3) as executor:
        stream_results = list(executor.map(_run_stream, goals))

    assert len(stream_results) == len(goals)


def test_stream_endpoint_repeated_connections_close_cleanly(app_client):
    for index in range(4):
        response = app_client.post(
            "/api/hca/run/stream",
            json={"goal": f"Repeated stream goal {index}"},
        )
        assert response.status_code == 200
        events = _parse_sse_events(response.text)
        assert events[0][0] == "status"
        assert any(name == "done" for name, _payload in events)
        assert events[-1][0] == "done"