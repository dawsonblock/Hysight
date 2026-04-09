from hca.runtime.runtime import Runtime
from hca.common.enums import RuntimeState, EventType
from hca.common.types import RunContext, ActionCandidate
from hca.storage.event_log import iter_events

def test_execution_event_order():
    rt = Runtime()
    context = RunContext(goal="test order")
    rt._current_state = RuntimeState.action_selection
    
    candidate = ActionCandidate(kind="echo", arguments={"text": "order test"})
    
    rt._execute_and_complete(context, candidate)
    
    events = list(iter_events(context.run_id))
    
    # Filter for relevant events
    exec_events = [e for e in events if e["event_type"] in [
        EventType.execution_started.value,
        EventType.execution_finished.value,
        EventType.state_transition.value
    ]]
    
    # Check sequence
    # 1. Transition to executing (if fresh run)
    # 2. execution_started
    # 3. execution_finished
    # 4. Transition to observing
    
    # In our implementation:
    # _set_state(executing)
    # append_event(execution_started)
    # execute()
    # append_event(execution_finished)
    # _set_state(observing)
    
    # Verify order
    types = [e["event_type"] for e in exec_events]
    # We only care about the relative order of these specific ones
    assert EventType.execution_started.value in types
    assert EventType.execution_finished.value in types
    
    start_idx = types.index(EventType.execution_started.value)
    finish_idx = types.index(EventType.execution_finished.value)
    assert start_idx < finish_idx
    
    # Check payload
    start_event = [e for e in exec_events if e["event_type"] == EventType.execution_started.value][0]
    assert start_event["payload"]["tool"] == "echo"
    
    finish_event = [e for e in exec_events if e["event_type"] == EventType.execution_finished.value][0]
    assert "receipt_id" in finish_event["payload"]
    assert finish_event["payload"]["status"] == "success"

def test_execution_failure():
    rt = Runtime()
    context = RunContext(goal="test failure")
    rt._current_state = RuntimeState.action_selection
    
    # unknown tool causes failure in current executor
    candidate = ActionCandidate(kind="non_existent_tool", arguments={})
    
    rt._execute_and_complete(context, candidate)
    
    assert rt._current_state == RuntimeState.failed
    
    events = list(iter_events(context.run_id))
    finish_event = [e for e in events if e["event_type"] == EventType.execution_finished.value][0]
    assert finish_event["payload"]["status"] == "failure"
    
    transition_to_failed = [e for e in events if e["event_type"] == EventType.state_transition.value and e["next_state"] == "failed"][0]
    assert transition_to_failed is not None

if __name__ == "__main__":
    test_execution_event_order()
    print("test_execution_event_order passed")
    test_execution_failure()
    print("test_execution_failure passed")
