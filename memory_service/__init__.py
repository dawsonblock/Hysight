"""
Memory service package.

Python implementation of the HCA memory contract (schema.json).
Drop-in replaceable with the Rust memvid-core HTTP service via MEMORY_BACKEND=rust + MEMORY_SERVICE_URL=<url>.
"""
from .controller import MemoryController
from .types import CandidateMemory, RetrievalQuery, RetrievalHit, MaintenanceReport

__all__ = ["MemoryController", "CandidateMemory", "RetrievalQuery", "RetrievalHit", "MaintenanceReport"]
