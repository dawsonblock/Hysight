"""Resolved repository and storage paths for the HCA runtime."""

from __future__ import annotations

import os
import sys
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parent
HCA_SRC_ROOT = PACKAGE_ROOT.parent
HCA_ROOT = HCA_SRC_ROOT.parent
REPO_ROOT = HCA_ROOT.parent


def ensure_sys_path(*paths: Path) -> None:
    for path in reversed(paths):
        path_str = str(path)
        if path_str not in sys.path:
            sys.path.insert(0, path_str)


def ensure_repo_root_on_sys_path() -> None:
    ensure_sys_path(REPO_ROOT)


def ensure_repo_paths_on_sys_path() -> None:
    ensure_sys_path(REPO_ROOT, HCA_SRC_ROOT)


def storage_root() -> Path:
    configured = os.environ.get("HCA_STORAGE_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    return REPO_ROOT / "storage"


def run_storage_dir(run_id: str) -> Path:
    return storage_root() / "runs" / run_id


def run_storage_path(run_id: str, *parts: str) -> Path:
    return run_storage_dir(run_id).joinpath(*parts)


def relative_run_storage_path(run_id: str, *parts: str) -> Path:
    return Path("storage").joinpath("runs", run_id, *parts)