"""Snapshot storage for run state."""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

from hca.common.time import to_iso, utc_now
from hca.common.types import SnapshotRecord
from hca.paths import run_storage_path
from hca.storage.runs import append_jsonl_record, read_jsonl_records


logger = logging.getLogger(__name__)


def _path(run_id: str) -> Path:
    return run_storage_path(run_id, "snapshots.jsonl")


def append_snapshot(run_id: str, snapshot_data: Dict[str, Any]) -> None:
    """Append a snapshot to the run's snapshots log."""
    path = _path(run_id)

    record = dict(snapshot_data)
    # Ensure run_id and timestamp are present
    if record.get("run_id") in (None, "unknown"):
        record["run_id"] = run_id
    if "timestamp" not in record:
        record["timestamp"] = to_iso(utc_now())

    append_jsonl_record(run_id, path, record)


def _scan_snapshots(run_id: str) -> Tuple[List[Dict[str, Any]], int]:
    path = _path(run_id)
    if not path.exists():
        return [], 0

    read_result = read_jsonl_records(path)
    snapshots: List[Dict[str, Any]] = []
    corruption_count = 1 if read_result.skipped_truncated_final_line else 0
    for record in read_result.records:
        try:
            validated = SnapshotRecord.model_validate(record)
            snapshots.append(validated.model_dump(mode="json"))
        except Exception:
            corruption_count += 1

    if corruption_count:
        logger.warning(
            "Skipped %s malformed snapshot record(s) for run %s",
            corruption_count,
            run_id,
        )
    return snapshots, corruption_count


def iter_snapshots(run_id: str) -> Iterator[Dict[str, Any]]:
    snapshots, _ = _scan_snapshots(run_id)
    yield from snapshots


def load_latest_valid_snapshot(run_id: str) -> Optional[Dict[str, Any]]:
    """Load the most recent valid snapshot for a run."""
    snapshots, corruption_count = _scan_snapshots(run_id)
    if not snapshots:
        return None

    latest = dict(snapshots[-1])
    latest["corruption_count"] = corruption_count
    return latest


def load_latest_snapshot(run_id: str) -> Optional[Dict[str, Any]]:
    return load_latest_valid_snapshot(run_id)
