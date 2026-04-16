"""Execution receipt storage."""

import json
from pathlib import Path
from typing import Any, Dict, Iterator

from hca.common.types import ExecutionReceipt
from hca.paths import run_storage_path
from hca.storage.runs import append_jsonl_record, read_jsonl_records


def _receipts_path(run_id: str) -> Path:
    return run_storage_path(run_id, "receipts.jsonl")


def append_receipt(run_id: str, receipt: Any) -> None:
    """Append an execution receipt to the run's receipts log."""
    path = _receipts_path(run_id)

    if isinstance(receipt, ExecutionReceipt):
        payload = receipt.model_dump(mode="json")
    elif isinstance(receipt, dict):
        payload = receipt
    else:
        raise TypeError(
            f"Expected ExecutionReceipt or dict, got {type(receipt)}"
        )

    append_jsonl_record(run_id, path, payload)


def iter_receipts(run_id: str) -> Iterator[Dict[str, Any]]:
    """Iterate over all receipts for a run as dictionaries."""
    yield from read_jsonl_records(_receipts_path(run_id)).records
