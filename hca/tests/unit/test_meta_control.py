from hca.meta.monitor import assess
from hca.common.types import WorkspaceItem, MetaAssessment, MemoryRecord, MemoryType
from hca.common.enums import ControlSignal

def test_memory_contradiction_triggers_replan():
    # Mock workspace with contradictory memory
    mem_rec = MemoryRecord(
        memory_type=MemoryType.identity,
        subject="user_name",
        content="Alice",
        contradiction_status=True
    )
    item = WorkspaceItem(
        source_module="memory",
        kind="memory_retrieval",
        content=[mem_rec.model_dump(mode="json")]
    )
    
    assessment = assess([item])
    assert assessment.recommended_transition == ControlSignal.replan
    assert "Contradictory memory" in assessment.explanation

def test_stale_memory_triggers_ask_user():
    # Mock workspace with stale memory
    mem_rec = MemoryRecord(
        memory_type=MemoryType.identity,
        subject="status",
        content="old",
        staleness=0.9
    )
    item = WorkspaceItem(
        source_module="memory",
        kind="memory_retrieval",
        content=[mem_rec.model_dump(mode="json")]
    )
    
    assessment = assess([item])
    assert assessment.recommended_transition == ControlSignal.ask_user
    assert "Stale memory detected" in assessment.explanation

if __name__ == "__main__":
    test_memory_contradiction_triggers_replan()
    print("test_memory_contradiction_triggers_replan passed")
    test_stale_memory_triggers_ask_user()
    print("test_stale_memory_triggers_ask_user passed")
