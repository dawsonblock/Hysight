"""Common package exports.

This module intentionally avoids eager imports so submodules such as
``hca.common.time`` can be imported without triggering circular imports
through ``hca.common.types``.
"""

from __future__ import annotations

from importlib import import_module


_TYPE_EXPORTS = {
    "RunContext",
    "WorkspaceItem",
    "ModuleProposal",
    "ActionBinding",
    "ActionCandidate",
    "MetaAssessment",
    "MemoryRecord",
    "RetrievalItem",
    "ContradictionResult",
    "PromotionCandidate",
    "ConflictRecord",
    "MissingInfoResult",
    "CapabilitySummary",
    "ExecutionReceipt",
    "ApprovalRequest",
    "ApprovalDecisionRecord",
    "ApprovalGrant",
    "ApprovalConsumption",
    "ArtifactRecord",
    "SnapshotRecord",
}

_ENUM_EXPORTS = {
    "RuntimeState",
    "EventType",
    "MemoryType",
    "ActionClass",
    "ApprovalDecision",
    "ControlSignal",
    "ReceiptStatus",
}

__all__ = sorted(_TYPE_EXPORTS | _ENUM_EXPORTS)


def __getattr__(name: str):
    if name in _TYPE_EXPORTS:
        module = import_module("hca.common.types")
        return getattr(module, name)
    if name in _ENUM_EXPORTS:
        module = import_module("hca.common.enums")
        return getattr(module, name)
    raise AttributeError(f"module 'hca.common' has no attribute {name!r}")
