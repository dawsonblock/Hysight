"""Memory store base classes and implementations."""

import json
import os
from typing import Iterator, List

from hca.common.types import MemoryRecord
from hca.common.enums import MemoryType
from hca.paths import run_storage_path


class MemoryStore:
    def __init__(
        self, run_id: str, memory_type: MemoryType, path: str
    ) -> None:
        self.run_id = run_id
        self.memory_type = memory_type
        # ensure directory exists
        self.path = run_storage_path(run_id, path)
        os.makedirs(self.path.parent, exist_ok=True)

    def append(self, record: MemoryRecord) -> None:
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(record.model_dump_json() + "\n")

    def write(self, record: MemoryRecord) -> None:
        """Compatibility alias for append-only memory writes."""
        self.append(record)

    def iter_records(self) -> Iterator[MemoryRecord]:
        if not self.path.exists():
            return
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                yield MemoryRecord.model_validate(data)

    def list_records(self) -> List[MemoryRecord]:
        return list(self.iter_records())

    def retrieve_by_subject(self, subject: str) -> List[MemoryRecord]:
        return [rec for rec in self.iter_records() if rec.subject == subject]
