"""File-backed JSONL storage for the autonomy subsystem.

Each autonomy surface (agents, schedules, inbox, checkpoints, audit) persists
to an append-only JSONL file under ``storage_root()/autonomy/``. Latest-record-
wins semantics are used on read: the last record for an id wins.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from hca.autonomy.checkpoint import (
    AutonomyBudgetLedger,
    AutonomyCheckpoint,
    AutonomyKillSwitch,
)
from hca.autonomy.triggers import (
    AutonomyAgent,
    AutonomyInboxItem,
    AutonomySchedule,
)
from hca.common.enums import (
    AgentStatus,
    CheckpointStatus,
    InboxStatus,
)
from hca.common.time import utc_now
from hca.paths import storage_root


_FILE_LOCKS: Dict[str, threading.RLock] = {}
_FILE_LOCKS_GUARD = threading.Lock()


AGENTS_FILE = "autonomy_agents.jsonl"
SCHEDULES_FILE = "autonomy_schedules.jsonl"
INBOX_FILE = "autonomy_inbox.jsonl"
CHECKPOINTS_FILE = "autonomy_checkpoints.jsonl"
AUDIT_FILE = "audit.jsonl"
KILL_SWITCH_FILE = "autonomy_kill_switch.jsonl"
BUDGET_LEDGER_FILE = "autonomy_budget_ledger.jsonl"
DEDUPE_FILE = "autonomy_dedupe.jsonl"


def _autonomy_root() -> Path:
    root = storage_root() / "autonomy"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _path(filename: str) -> Path:
    return _autonomy_root() / filename


def _file_lock(path: Path) -> threading.RLock:
    key = str(path)
    with _FILE_LOCKS_GUARD:
        lock = _FILE_LOCKS.get(key)
        if lock is None:
            lock = threading.RLock()
            _FILE_LOCKS[key] = lock
        return lock


def _append(path: Path, record: Dict[str, Any]) -> None:
    line = json.dumps(record, default=str)
    with _file_lock(path):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(line)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())


def _read_all(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    records: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as handle:
        for raw_line in handle:
            stripped = raw_line.strip()
            if not stripped:
                continue
            try:
                record = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if isinstance(record, dict):
                records.append(record)
    return records


def _latest_by_key(
    records: Iterable[Dict[str, Any]], key: str
) -> Dict[str, Dict[str, Any]]:
    latest: Dict[str, Dict[str, Any]] = {}
    for record in records:
        identifier = record.get(key)
        if not isinstance(identifier, str):
            continue
        latest[identifier] = record
    return latest


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------


def save_agent(agent: AutonomyAgent) -> AutonomyAgent:
    agent.updated_at = utc_now()
    _append(_path(AGENTS_FILE), agent.model_dump(mode="json"))
    return agent


def get_agent(agent_id: str) -> Optional[AutonomyAgent]:
    latest = _latest_by_key(_read_all(_path(AGENTS_FILE)), "agent_id")
    record = latest.get(agent_id)
    if record is None:
        return None
    return AutonomyAgent.model_validate(record)


def list_agents() -> List[AutonomyAgent]:
    latest = _latest_by_key(_read_all(_path(AGENTS_FILE)), "agent_id")
    return [AutonomyAgent.model_validate(r) for r in latest.values()]


def set_agent_status(agent_id: str, status: AgentStatus) -> AutonomyAgent:
    agent = get_agent(agent_id)
    if agent is None:
        raise LookupError(f"agent {agent_id} not found")
    agent.status = status
    return save_agent(agent)


# ---------------------------------------------------------------------------
# Schedules
# ---------------------------------------------------------------------------


def save_schedule(schedule: AutonomySchedule) -> AutonomySchedule:
    schedule.updated_at = utc_now()
    _append(_path(SCHEDULES_FILE), schedule.model_dump(mode="json"))
    return schedule


def list_schedules() -> List[AutonomySchedule]:
    latest = _latest_by_key(_read_all(_path(SCHEDULES_FILE)), "schedule_id")
    return [AutonomySchedule.model_validate(r) for r in latest.values()]


def get_schedule(schedule_id: str) -> Optional[AutonomySchedule]:
    latest = _latest_by_key(_read_all(_path(SCHEDULES_FILE)), "schedule_id")
    record = latest.get(schedule_id)
    if record is None:
        return None
    return AutonomySchedule.model_validate(record)


def list_due_schedules(now: Optional[datetime] = None) -> List[AutonomySchedule]:
    reference = now or utc_now()
    due: List[AutonomySchedule] = []
    for schedule in list_schedules():
        if not schedule.enabled:
            continue
        if schedule.last_fired_at is None:
            due.append(schedule)
            continue
        elapsed = (reference - schedule.last_fired_at).total_seconds()
        if elapsed >= schedule.interval_seconds:
            due.append(schedule)
    return due


def mark_schedule_fired(
    schedule_id: str, fired_at: Optional[datetime] = None
) -> Optional[AutonomySchedule]:
    schedule = get_schedule(schedule_id)
    if schedule is None:
        return None
    schedule.last_fired_at = fired_at or utc_now()
    return save_schedule(schedule)


# ---------------------------------------------------------------------------
# Inbox
# ---------------------------------------------------------------------------


def enqueue_inbox_item(item: AutonomyInboxItem) -> AutonomyInboxItem:
    _append(_path(INBOX_FILE), item.model_dump(mode="json"))
    return item


def list_inbox_items(
    agent_id: Optional[str] = None,
    status: Optional[InboxStatus] = None,
) -> List[AutonomyInboxItem]:
    latest = _latest_by_key(_read_all(_path(INBOX_FILE)), "item_id")
    items = [AutonomyInboxItem.model_validate(r) for r in latest.values()]
    if agent_id is not None:
        items = [i for i in items if i.agent_id == agent_id]
    if status is not None:
        items = [i for i in items if i.status == status]
    return items


def claim_inbox_item(agent_id: str) -> Optional[AutonomyInboxItem]:
    path = _path(INBOX_FILE)
    with _file_lock(path):
        candidates = sorted(
            list_inbox_items(agent_id=agent_id, status=InboxStatus.pending),
            key=lambda item: item.created_at,
        )
        if not candidates:
            return None
        item = candidates[0]
        item.status = InboxStatus.claimed
        item.claimed_at = utc_now()
        _append(path, item.model_dump(mode="json"))
        return item


def cancel_inbox_item(item_id: str) -> Optional[AutonomyInboxItem]:
    path = _path(INBOX_FILE)
    with _file_lock(path):
        latest = _latest_by_key(_read_all(path), "item_id")
        record = latest.get(item_id)
        if record is None:
            return None
        item = AutonomyInboxItem.model_validate(record)
        if item.status in (InboxStatus.cancelled, InboxStatus.completed):
            return item
        item.status = InboxStatus.cancelled
        _append(path, item.model_dump(mode="json"))
        return item


def complete_inbox_item(item_id: str) -> Optional[AutonomyInboxItem]:
    path = _path(INBOX_FILE)
    with _file_lock(path):
        latest = _latest_by_key(_read_all(path), "item_id")
        record = latest.get(item_id)
        if record is None:
            return None
        item = AutonomyInboxItem.model_validate(record)
        item.status = InboxStatus.completed
        _append(path, item.model_dump(mode="json"))
        return item


# ---------------------------------------------------------------------------
# Checkpoints
# ---------------------------------------------------------------------------


def save_checkpoint(checkpoint: AutonomyCheckpoint) -> AutonomyCheckpoint:
    checkpoint.checkpointed_at = utc_now()
    _append(_path(CHECKPOINTS_FILE), checkpoint.model_dump(mode="json"))
    return checkpoint


def _checkpoint_key(record: Dict[str, Any]) -> Optional[str]:
    agent_id = record.get("agent_id")
    trigger_id = record.get("trigger_id")
    if not isinstance(agent_id, str) or not isinstance(trigger_id, str):
        return None
    return f"{agent_id}:{trigger_id}"


def _latest_checkpoints() -> Dict[str, Dict[str, Any]]:
    latest: Dict[str, Dict[str, Any]] = {}
    for record in _read_all(_path(CHECKPOINTS_FILE)):
        key = _checkpoint_key(record)
        if key is None:
            continue
        latest[key] = record
    return latest


def load_checkpoint(
    agent_id: str, trigger_id: str
) -> Optional[AutonomyCheckpoint]:
    key = f"{agent_id}:{trigger_id}"
    record = _latest_checkpoints().get(key)
    if record is None:
        return None
    return AutonomyCheckpoint.model_validate(record)


def list_checkpoints(
    agent_id: Optional[str] = None,
) -> List[AutonomyCheckpoint]:
    checkpoints = [
        AutonomyCheckpoint.model_validate(r)
        for r in _latest_checkpoints().values()
    ]
    if agent_id is not None:
        checkpoints = [c for c in checkpoints if c.agent_id == agent_id]
    checkpoints.sort(key=lambda c: c.checkpointed_at, reverse=True)
    return checkpoints


def list_active_autonomy_runs() -> List[AutonomyCheckpoint]:
    active_statuses = {
        CheckpointStatus.launched,
        CheckpointStatus.observing,
        CheckpointStatus.awaiting_approval,
        CheckpointStatus.retry_scheduled,
    }
    return [
        checkpoint
        for checkpoint in list_checkpoints()
        if checkpoint.status in active_statuses and checkpoint.run_id
    ]


# ---------------------------------------------------------------------------
# Audit log (pre-run autonomy events)
# ---------------------------------------------------------------------------


def append_autonomy_audit(record: Dict[str, Any]) -> None:
    enriched = dict(record)
    enriched.setdefault("timestamp", utc_now().isoformat())
    _append(_path(AUDIT_FILE), enriched)


def read_autonomy_audit() -> List[Dict[str, Any]]:
    return _read_all(_path(AUDIT_FILE))


# ---------------------------------------------------------------------------
# Kill switch (single global record; latest wins)
# ---------------------------------------------------------------------------


def load_kill_switch() -> AutonomyKillSwitch:
    records = _read_all(_path(KILL_SWITCH_FILE))
    if not records:
        return AutonomyKillSwitch()
    return AutonomyKillSwitch.model_validate(records[-1])


def set_kill_switch(
    *,
    active: bool,
    reason: Optional[str] = None,
    set_by: Optional[str] = None,
) -> AutonomyKillSwitch:
    current = load_kill_switch()
    now = utc_now()
    record = AutonomyKillSwitch(
        active=active,
        reason=reason if active else None,
        set_at=now if active else current.set_at,
        cleared_at=None if active else now,
        set_by=set_by if active else current.set_by,
    )
    _append(_path(KILL_SWITCH_FILE), record.model_dump(mode="json"))
    return record


# ---------------------------------------------------------------------------
# Budget ledger (durable per-agent counters)
# ---------------------------------------------------------------------------


def _latest_ledgers() -> Dict[str, Dict[str, Any]]:
    return _latest_by_key(_read_all(_path(BUDGET_LEDGER_FILE)), "agent_id")


def get_budget_ledger(agent_id: str) -> AutonomyBudgetLedger:
    record = _latest_ledgers().get(agent_id)
    if record is None:
        return AutonomyBudgetLedger(agent_id=agent_id)
    return AutonomyBudgetLedger.model_validate(record)


def list_budget_ledgers() -> List[AutonomyBudgetLedger]:
    ledgers = [
        AutonomyBudgetLedger.model_validate(r)
        for r in _latest_ledgers().values()
    ]
    ledgers.sort(
        key=lambda ledger: ledger.updated_at or utc_now(),
        reverse=True,
    )
    return ledgers


def update_budget_ledger(
    agent_id: str,
    *,
    launched_runs_delta: int = 0,
    active_runs_delta: int = 0,
    steps_delta: int = 0,
    retries_delta: int = 0,
    run_started: bool = False,
    run_completed: bool = False,
    budget_breach: bool = False,
) -> AutonomyBudgetLedger:
    path = _path(BUDGET_LEDGER_FILE)
    with _file_lock(path):
        ledger = get_budget_ledger(agent_id)
        ledger.launched_runs_total = max(
            0, ledger.launched_runs_total + launched_runs_delta
        )
        ledger.active_runs = max(0, ledger.active_runs + active_runs_delta)
        ledger.total_steps_observed = max(
            0, ledger.total_steps_observed + steps_delta
        )
        ledger.total_retries_used = max(
            0, ledger.total_retries_used + retries_delta
        )
        now = utc_now()
        if run_started:
            ledger.last_run_started_at = now
        if run_completed:
            ledger.last_run_completed_at = now
        if budget_breach:
            ledger.last_budget_breach_at = now
        ledger.updated_at = now
        _append(path, ledger.model_dump(mode="json"))
        return ledger


# ---------------------------------------------------------------------------
# Trigger dedupe (durable dedupe_key → (trigger_id, run_id) mapping)
# ---------------------------------------------------------------------------


def _latest_dedupe() -> Dict[str, Dict[str, Any]]:
    return _latest_by_key(_read_all(_path(DEDUPE_FILE)), "dedupe_key")


def find_dedupe(dedupe_key: str) -> Optional[Dict[str, Any]]:
    if not dedupe_key:
        return None
    return _latest_dedupe().get(dedupe_key)


def record_dedupe(
    *,
    dedupe_key: str,
    trigger_id: str,
    agent_id: str,
    run_id: Optional[str] = None,
) -> None:
    if not dedupe_key:
        return
    _append(
        _path(DEDUPE_FILE),
        {
            "dedupe_key": dedupe_key,
            "trigger_id": trigger_id,
            "agent_id": agent_id,
            "run_id": run_id,
            "recorded_at": utc_now().isoformat(),
        },
    )


def count_dedupe_records() -> int:
    return len(_latest_dedupe())
