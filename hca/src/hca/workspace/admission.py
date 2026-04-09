"""Admission helper wrappers for workspace."""

from typing import List, Tuple

from hca.workspace.workspace import Workspace
from hca.common.types import WorkspaceItem


def admit_items(workspace: Workspace, candidates: List[WorkspaceItem]) -> Tuple[List[WorkspaceItem], List[WorkspaceItem], List[WorkspaceItem]]:
    return workspace.admit(candidates)