"""Procedural memory store implementation."""

from hca.common.enums import MemoryType
from hca.memory.interfaces import MemoryStore


class ProceduralStore(MemoryStore):
    def __init__(self, run_id: str) -> None:
        super().__init__(run_id, MemoryType.procedural, "memory/procedural.jsonl")