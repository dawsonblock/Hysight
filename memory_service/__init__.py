"""
Memory service package.

Python implementation of the HCA memory contract (schema.json).
Drop-in replaceable with the Rust memvid-core HTTP service via MEMORY_BACKEND=rust + MEMORY_SERVICE_URL=<url>.
"""
from .config import MemoryConfigurationError, MemorySettings
from .controller import MemoryController
from .types import (
	CandidateMemory,
	DeleteMemoryResponse,
	MaintenanceReport,
	MemoryListItem,
	MemoryListResponse,
	Provenance,
	RetrievalHit,
	RetrievalQuery,
	RetrievalResponse,
)

__all__ = [
	"MemoryConfigurationError",
	"MemoryController",
	"MemoryListItem",
	"MemoryListResponse",
	"MemorySettings",
	"CandidateMemory",
	"DeleteMemoryResponse",
	"RetrievalQuery",
	"RetrievalHit",
	"RetrievalResponse",
	"MaintenanceReport",
	"Provenance",
]
