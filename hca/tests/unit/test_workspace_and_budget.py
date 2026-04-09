from hca.workspace.workspace import Workspace
from hca.common.types import WorkspaceItem, RunContext, ModuleProposal, MetaAssessment
from hca.runtime.runtime import Runtime
from hca.common.enums import ControlSignal, RuntimeState

def test_workspace_summary():
    ws = Workspace()
    ws.items = [
        WorkspaceItem(source_module="m1", kind="k1", content="c1"),
        WorkspaceItem(source_module="m1", kind="k1", content="c2"),
        WorkspaceItem(source_module="m1", kind="k2", content="c3"),
    ]
    summary = ws.summary()
    assert summary == {"k1": 2, "k2": 1}

def test_replan_budget_exhaustion(monkeypatch):
    import hca.runtime.runtime

    def mock_assess(*args, **kwargs):
        return MetaAssessment(
            overall_confidence=1.0,
            recommended_transition=ControlSignal.replan,
            explanation="keep replanning"
        )
    monkeypatch.setattr(hca.runtime.runtime, "assess", mock_assess)
    
    rt = Runtime(replan_budget=2)
    
    for m in rt.modules:
        def mock_propose(run_id):
            return ModuleProposal(source_module="test", candidate_items=[])
        monkeypatch.setattr(m, "propose", mock_propose)
    
    rt.run("test budget")
    
    # It should have decremented twice and then stopped
    assert rt._remaining_replan == 0

if __name__ == "__main__":
    # Use pytest to handle monkeypatching
    import sys
    import pytest
    sys.exit(pytest.main([__file__]))
