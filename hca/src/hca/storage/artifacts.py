"""Storage for artifact records."""

from pathlib import Path
from typing import Iterator, Dict, Any

from hca.paths import run_storage_path
from hca.storage.runs import append_jsonl_record, read_jsonl_records


def _path(run_id: str) -> Path:
    return run_storage_path(run_id, "artifacts.jsonl")


def append_artifact(run_id: str, record: Dict[str, Any]) -> None:
    path = _path(run_id)
    append_jsonl_record(run_id, path, record)


def iter_artifacts(run_id: str) -> Iterator[Dict[str, Any]]:
    yield from read_jsonl_records(_path(run_id)).records
