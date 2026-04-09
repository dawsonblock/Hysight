"""Semantic memory store implementation."""

from hca.common.enums import MemoryType
from hca.memory.interfaces import MemoryStore


class SemanticStore(MemoryStore):
    def __init__(self, run_id: str) -> None:
        super().__init__(run_id, MemoryType.semantic, "memory/semantic.jsonl")