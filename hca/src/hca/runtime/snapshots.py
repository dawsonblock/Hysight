"""Helpers for building stable runtime snapshots."""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Optional

from hca.common.enums import MemoryType, RuntimeState
from hca.common.types import (
    ActionCandidate,
    ArtifactSummary,
    SnapshotRecord,
    WorkflowBudget,
    WorkflowCheckpoint,
    WorkflowPlan,
    WorkflowStepRecord,
    WorkspaceItem,
)
from hca.memory.episodic_store import EpisodicStore
from hca.memory.identity_store import IdentityStore
from hca.memory.procedural_store import ProceduralStore
from hca.memory.semantic_store import SemanticStore


def _workspace_items(
    workspace_or_items: Any,
) -> List[WorkspaceItem]:
    if workspace_or_items is None:
        return []
    if hasattr(workspace_or_items, "items"):
        return list(workspace_or_items.items)
    return list(workspace_or_items)


def summarize_workspace_items(
    workspace_or_items: Any,
) -> Dict[str, Any]:
    items = _workspace_items(workspace_or_items)
    counts = Counter(item.kind for item in items)
    return {
        "item_count": len(items),
        "kinds": dict(counts),
    }


def count_memory_records(run_id: str) -> Dict[str, int]:
    stores = (
        (MemoryType.episodic.value, EpisodicStore(run_id)),
        (MemoryType.semantic.value, SemanticStore(run_id)),
        (MemoryType.procedural.value, ProceduralStore(run_id)),
        (MemoryType.identity.value, IdentityStore(run_id)),
    )
    counts: Dict[str, int] = {}
    for name, store in stores:
        counts[name] = sum(1 for _ in store.iter_records())
    return counts


def build_runtime_snapshot(
    run_id: str,
    state: RuntimeState,
    workspace_or_items: Any,
    selected_action: Optional[ActionCandidate] = None,
    pending_approval_id: Optional[str] = None,
    latest_receipt_id: Optional[str] = None,
    memory_counts: Optional[Dict[str, int]] = None,
    promotion_candidates: Optional[List[Dict[str, Any]]] = None,
    active_workflow: Optional[WorkflowPlan] = None,
    workflow_budget: Optional[WorkflowBudget] = None,
    workflow_checkpoint: Optional[WorkflowCheckpoint] = None,
    workflow_step_history: Optional[List[WorkflowStepRecord]] = None,
    workflow_artifacts: Optional[List[ArtifactSummary]] = None,
) -> Dict[str, Any]:
    items = _workspace_items(workspace_or_items)
    snapshot = SnapshotRecord(
        run_id=run_id,
        state=state,
        workspace=items,
        memory_summary=memory_counts or count_memory_records(run_id),
        pending_approval=pending_approval_id,
        latest_receipt=latest_receipt_id,
        workspace_summary=summarize_workspace_items(items),
        pending_approval_id=pending_approval_id,
        selected_action=(
            selected_action.model_dump(mode="json")
            if selected_action is not None
            else None
        ),
        active_workflow=active_workflow,
        workflow_budget=workflow_budget,
        workflow_checkpoint=workflow_checkpoint,
        workflow_step_history=workflow_step_history or [],
        workflow_artifacts=workflow_artifacts or [],
    )
    data = snapshot.model_dump(mode="json")
    if promotion_candidates:
        data["promotion_candidates"] = promotion_candidates
    return data
