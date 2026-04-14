"""Persist and retrieve run metadata."""

from __future__ import annotations

import json
import os
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

try:  # pragma: no cover - Windows fallback keeps import optional.
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None

from hca.common.types import RunContext
from hca.paths import run_storage_path


_RUN_LOCKS: dict[str, threading.RLock] = {}
_RUN_LOCKS_GUARD = threading.Lock()


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


@contextmanager
def run_operation_lock(run_id: str) -> Iterator[None]:
    """Serialize read-modify-write operations for a single run."""

    process_lock = _run_lock(run_id)
    process_lock.acquire()
    file_handle = None

    try:
        if fcntl is not None:
            lock_path = _run_lock_path(run_id)
            os.makedirs(lock_path.parent, exist_ok=True)
            file_handle = open(lock_path, "a+", encoding="utf-8")
            fcntl.flock(file_handle.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        if file_handle is not None:
            try:
                fcntl.flock(file_handle.fileno(), fcntl.LOCK_UN)
            finally:
                file_handle.close()
        process_lock.release()


def save_run(context: RunContext) -> None:
    """Persist the run context to disk."""
    path = _run_path(context.run_id)
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
