from hca.common.types import RetrievalItem, WorkspaceItem, MemoryRecord
from hca.common.enums import ControlSignal, MemoryType
from hca.meta.monitor import assess
from hca.meta.conflict_detector import detect_conflicts
from hca.meta.missing_info import detect_missing_information
from hca.meta.self_model import check_self_limitations
from hca.workspace.workspace import Workspace


def test_monitor_contradiction():
    # Item marked as contradictory
    memory_record = MemoryRecord(
        run_id="test",
        memory_type=MemoryType.episodic,
        subject="test",
        content="test",
        contradiction_status=True
    )
    item = WorkspaceItem(
        kind="memory_retrieval",
        source_module="test",
        content=[
            RetrievalItem(
                record=memory_record,
                confidence=1.0,
                contradiction=True,
                staleness=0.0,
                memory_type=MemoryType.episodic,
            )
        ]
    )
    assessment = assess([item])
    assert assessment.recommended_transition == ControlSignal.replan
    assert "Contradictory" in assessment.explanation


def test_conflict_detector():
    i1 = WorkspaceItem(
        item_id="1",
        source_module="test",
        kind="action_suggestion",
        content={"action": "echo"},
    )
    i2 = WorkspaceItem(
        item_id="2",
        source_module="test",
        kind="action_suggestion",
        content={"action": "store_note"},
    )

    conflicts = detect_conflicts([i1, i2])
    assert len(conflicts) == 1
    assert conflicts[0].item_ids == ["1", "2"]


def test_missing_info_detector():
    item = WorkspaceItem(
        item_id="1",
        source_module="test",
        kind="action_suggestion",
        content={"action": "store_note", "args": {}},
    )
    missing = detect_missing_information([item])
    assert len(missing) == 1
    assert missing[0].item_id == "1"


def test_missing_info_detector_flags_invalid_fields():
    item = WorkspaceItem(
        item_id="2",
        source_module="test",
        kind="action_suggestion",
        content={
            "action": "echo",
            "args": {"text": "hello", "path": "oops.txt"},
        },
    )
    missing = detect_missing_information([item])
    assert len(missing) == 1
    assert missing[0].invalid_fields == ["path"]


def test_self_model_limits():
    item = WorkspaceItem(
        item_id="1",
        source_module="test",
        kind="action_suggestion",
        content={"action": "calculate"},
    )
    limits = check_self_limitations([item])
    assert len(limits) == 1
    assert "calculate" in limits[0]


def test_workspace_admit_evict():
    ws = Workspace(capacity=2)
    i1 = WorkspaceItem(
        item_id="1",
        source_module="test",
        kind="test",
        content="1",
        confidence=0.9,
    )
    i2 = WorkspaceItem(
        item_id="2",
        source_module="test",
        kind="test",
        content="2",
        confidence=0.8,
    )
    i3 = WorkspaceItem(
        item_id="3",
        source_module="test",
        kind="test",
        content="3",
        confidence=0.95,
    )

    ws.admit([i1, i2])
    assert len(ws.items) == 2

    ws.admit([i3])
    assert len(ws.items) == 2
    # i2 should be evicted (lowest confidence)
    ids = [i.item_id for i in ws.items]
    assert "1" in ids
    assert "3" in ids
    assert "2" not in ids


if __name__ == "__main__":
    test_monitor_contradiction()
    print("test_monitor_contradiction passed")
    test_conflict_detector()
    print("test_conflict_detector passed")
    test_missing_info_detector()
    print("test_missing_info_detector passed")
    test_self_model_limits()
    print("test_self_model_limits passed")
    test_workspace_admit_evict()
    print("test_workspace_admit_evict passed")
