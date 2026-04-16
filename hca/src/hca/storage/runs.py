"""Persist and retrieve run metadata."""

from __future__ import annotations

import json
import os
import tempfile
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Optional

try:  # pragma: no cover - Windows fallback keeps import optional.
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None

from hca.common.types import RunContext
from hca.paths import run_storage_path


_RUN_LOCKS: dict[str, threading.RLock] = {}
_RUN_LOCKS_GUARD = threading.Lock()
_RUN_LOCK_DEPTH = threading.local()


class JSONLReplayError(RuntimeError):
    """Raised when append-only JSONL storage is malformed."""


@dataclass(frozen=True)
class JSONLReadResult:
    records: list[dict[str, Any]]
    next_offset: int
    skipped_truncated_final_line: bool = False


def _run_path(run_id: str) -> Path:
    return run_storage_path(run_id, "run.json")


def _run_lock_path(run_id: str) -> Path:
    return run_storage_path(run_id, "run.lock")


def _run_lock(run_id: str) -> threading.RLock:
    with _RUN_LOCKS_GUARD:
        lock = _RUN_LOCKS.get(run_id)
        if lock is None:
            lock = threading.RLock()
            _RUN_LOCKS[run_id] = lock
        return lock


def _fsync_directory(path: Path) -> None:
    try:
        directory_fd = os.open(path, os.O_RDONLY)
    except OSError:
        return

    try:
        os.fsync(directory_fd)
    except OSError:
        pass
    finally:
        os.close(directory_fd)


def _thread_lock_depths() -> dict[str, int]:
    depths = getattr(_RUN_LOCK_DEPTH, "depths", None)
    if depths is None:
        depths = {}
        _RUN_LOCK_DEPTH.depths = depths
    return depths


@contextmanager
def run_operation_lock(run_id: str) -> Iterator[None]:
    """Serialize read-modify-write operations for a single run."""

    process_lock = _run_lock(run_id)
    process_lock.acquire()
    depths = _thread_lock_depths()
    depth = depths.get(run_id, 0)
    depths[run_id] = depth + 1
    file_handle = None

    try:
        if depth == 0 and fcntl is not None:
            lock_path = _run_lock_path(run_id)
            os.makedirs(lock_path.parent, exist_ok=True)
            file_handle = open(lock_path, "a+", encoding="utf-8")
            fcntl.flock(file_handle.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        remaining_depth = depths.get(run_id, 1) - 1
        if remaining_depth <= 0:
            depths.pop(run_id, None)
        else:
            depths[run_id] = remaining_depth
        if file_handle is not None:
            try:
                fcntl.flock(file_handle.fileno(), fcntl.LOCK_UN)
            finally:
                file_handle.close()
        process_lock.release()


def append_jsonl_record(run_id: str, path: Path, record: Any) -> None:
    """Append one JSON object line under the run lock and fsync it."""
    line = json.dumps(record, default=str)
    with run_operation_lock(run_id):
        os.makedirs(path.parent, exist_ok=True)
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(line)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        _fsync_directory(path.parent)


def read_jsonl_records(
    path: Path,
    *,
    start_offset: int = 0,
) -> JSONLReadResult:
    """Read JSONL records while tolerating only a torn final line.

    When the last line is truncated at EOF, replay skips it and reports the
    offset of the truncated line so tailing readers can retry later.
    """
    if not path.exists():
        return JSONLReadResult(records=[], next_offset=max(start_offset, 0))

    file_size = path.stat().st_size
    safe_offset = min(max(start_offset, 0), file_size)
    records: list[dict[str, Any]] = []
    next_offset = safe_offset

    with open(path, "rb") as handle:
        handle.seek(safe_offset)
        while True:
            record_offset = handle.tell()
            raw_line = handle.readline()
            if raw_line == b"":
                break

            next_offset = handle.tell()
            if not raw_line.strip():
                continue

            try:
                record = json.loads(raw_line.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                truncated_final_line = (
                    next_offset == file_size and not raw_line.endswith(b"\n")
                )
                if truncated_final_line:
                    return JSONLReadResult(
                        records=records,
                        next_offset=record_offset,
                        skipped_truncated_final_line=True,
                    )
                raise JSONLReplayError(
                    f"Malformed JSONL record in {path} at byte offset {record_offset}"
                ) from exc

            if not isinstance(record, dict):
                raise JSONLReplayError(
                    f"JSONL record in {path} at byte offset {record_offset} is not an object"
                )
            records.append(record)

    return JSONLReadResult(records=records, next_offset=next_offset)


def save_run(context: RunContext) -> None:
    """Persist the run context to disk."""
    path = _run_path(context.run_id)
    with run_operation_lock(context.run_id):
        os.makedirs(path.parent, exist_ok=True)
        fd, temp_path = tempfile.mkstemp(
            prefix=f"{path.stem}-",
            suffix=path.suffix,
            dir=path.parent,
            text=True,
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(
                    context.model_dump(),
                    handle,
                    default=str,
                    indent=2,
                )
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, path)
            _fsync_directory(path.parent)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)


def load_run(run_id: str) -> Optional[RunContext]:
    """Load the run context from disk."""
    path = _run_path(run_id)
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return RunContext.model_validate(data)
