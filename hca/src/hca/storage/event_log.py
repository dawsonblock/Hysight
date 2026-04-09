"""Append‑only event log for runs."""

import json
import os
from pathlib import Path
from typing import Dict, Iterator, Optional, Any

from hca.common.types import RunContext
from hca.common.time import utc_now as _now
from hca.common.enums import EventType, RuntimeState


def _events_path(run_id: str) -> Path:
    return Path(f"storage/runs/{run_id}/events.jsonl")


def append_event(
    run: RunContext,
    event_type: EventType,
    actor: str,
    payload: Dict[str, Any],
    provenance: Optional[list] = None,
    prior_state: Optional[RuntimeState] = None,
    next_state: Optional[RuntimeState] = None,
) -> None:
    """Append an event to the run's event log."""
    path = _events_path(run.run_id)
    os.makedirs(path.parent, exist_ok=True)
    record = {
        "event_id": os.urandom(8).hex(),
        "run_id": run.run_id,
        "timestamp": _now().isoformat(),
        "event_type": event_type.value,
        "actor": actor,
        "payload": payload,
        "provenance": provenance or [],
        "prior_state": prior_state.value if prior_state else None,
        "next_state": next_state.value if next_state else None,
    }
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def iter_events(run_id: str) -> Iterator[Dict[str, Any]]:
    """Iterate over all events for a run."""
    path = _events_path(run_id)
    if not path.exists():
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)