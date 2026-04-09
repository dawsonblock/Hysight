"""
Process-level singleton for the MemoryController.

Import pattern:
    from memory_service.singleton import get_controller
"""
from __future__ import annotations

import os
from typing import Optional

from .controller import MemoryController

_controller: Optional[MemoryController] = None


def get_controller() -> MemoryController:
    """Return (or lazily create) the shared MemoryController instance."""
    global _controller
    if _controller is None:
        storage_dir = os.environ.get("MEMORY_STORAGE_DIR", "storage/memory")
        _controller = MemoryController(storage_dir=storage_dir)
    return _controller
