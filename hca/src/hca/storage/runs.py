"""Persist and retrieve run metadata."""

import json
import os
from pathlib import Path
from typing import Optional

from hca.common.types import RunContext


def _run_path(run_id: str) -> Path:
    return Path(f"storage/runs/{run_id}/run.json")


def save_run(context: RunContext) -> None:
    """Persist the run context to disk."""
    path = _run_path(context.run_id)
    os.makedirs(path.parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(context.model_dump(), f, default=str, indent=2)


def load_run(run_id: str) -> Optional[RunContext]:
    """Load the run context from disk."""
    path = _run_path(run_id)
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return RunContext.model_validate(data)