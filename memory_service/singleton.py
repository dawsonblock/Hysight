"""
Process-level singleton for the MemoryController.

Import pattern:
    from memory_service.singleton import get_controller
"""
from __future__ import annotations

from typing import Optional

from .config import validate_memory_backend_startup
from .controller import MemoryController

_controller: Optional[MemoryController] = None


def get_controller() -> MemoryController:
    """Return (or lazily create) the shared MemoryController instance."""
    global _controller
    if _controller is None:
        settings = validate_memory_backend_startup()
        _controller = MemoryController(settings=settings)
    return _controller
