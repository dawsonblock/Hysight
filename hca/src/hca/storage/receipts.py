"""Execution receipt storage."""

import json
import os
from pathlib import Path
from typing import Dict, Iterator, Optional, Any
from hca.common.types import ExecutionReceipt

def _receipts_path(run_id: str) -> Path:
    return Path(f"storage/runs/{run_id}/receipts.jsonl")

def append_receipt(run_id: str, receipt: Any) -> None:
    """Append an execution receipt to the run's receipts log."""
    path = _receipts_path(run_id)
    os.makedirs(path.parent, exist_ok=True)
    
    if isinstance(receipt, ExecutionReceipt):
        line = receipt.model_dump_json()
    elif isinstance(receipt, dict):
        line = json.dumps(receipt)
    else:
        raise TypeError(f"Expected ExecutionReceipt or dict, got {type(receipt)}")
        
    with open(path, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def iter_receipts(run_id: str) -> Iterator[Dict[str, Any]]:
    """Iterate over all receipts for a run as dictionaries."""
    path = _receipts_path(run_id)
    if not path.exists():
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                yield json.loads(line)
            except Exception:
                continue
