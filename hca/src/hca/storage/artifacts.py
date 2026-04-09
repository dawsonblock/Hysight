"""Storage for artifact records."""

import json
import os
from pathlib import Path
from typing import Iterator, Dict, Any


def _path(run_id: str) -> Path:
    return Path(f"storage/runs/{run_id}/artifacts.jsonl")


def append_artifact(run_id: str, record: Dict[str, Any]) -> None:
    path = _path(run_id)
    os.makedirs(path.parent, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def iter_artifacts(run_id: str) -> Iterator[Dict[str, Any]]:
    path = _path(run_id)
    if not path.exists():
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)