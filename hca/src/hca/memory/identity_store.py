"""Identity memory store implementation."""

from hca.common.enums import MemoryType
from hca.memory.interfaces import MemoryStore


class IdentityStore(MemoryStore):
    def __init__(self, run_id: str) -> None:
        super().__init__(run_id, MemoryType.identity, "memory/identity.jsonl")