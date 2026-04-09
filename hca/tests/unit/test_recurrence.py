from hca.workspace.workspace import Workspace
from hca.workspace.recurrence import run_recurrence
from hca.common.types import WorkspaceItem, RunContext
import uuid

def test_recurrence_resolves_contradiction():
    ws = Workspace()
    # Mock two conflicting action suggestions
    # We must give them unique item_ids for the resolution logic to work
    item_a = WorkspaceItem(
        item_id="item_a",
        source_module="module_a",
        kind="action_suggestion",
        content={"action": "echo", "args": {"text": "A"}},
        confidence=0.7
    )
    item_b = WorkspaceItem(
        item_id="item_b",
        source_module="module_b",
        kind="action_suggestion",
        content={"action": "echo", "args": {"text": "B"}},
        confidence=0.9
    )
    ws.admit([item_a, item_b])
    
    # Check if they were both admitted
    assert len(ws.items) == 2
    
    # Run recurrence
    run_recurrence(ws, depth=1)
    
    # Should resolve to the higher confidence one
    # Note: Recurrence also adds a task_plan and action_critique
    # So we check if there is only 1 action_suggestion
    actions = [item for item in ws.items if item.kind == "action_suggestion"]
    assert len(actions) == 1
    assert actions[0].content["args"]["text"] == "B"

if __name__ == "__main__":
    test_recurrence_resolves_contradiction()
    print("test_recurrence_resolves_contradiction passed")
