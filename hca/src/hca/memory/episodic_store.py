"""Episodic memory store implementation."""

from hca.common.enums import MemoryType
from hca.common.types import MemoryRecord
from hca.memory.interfaces import MemoryStore


class EpisodicStore(MemoryStore):
    def __init__(self, run_id: str) -> None:
        super().__init__(run_id, MemoryType.episodic, "memory/episodic.jsonl")