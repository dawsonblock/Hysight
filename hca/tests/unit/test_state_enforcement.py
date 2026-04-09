import pytest
from hca.runtime.runtime import Runtime
from hca.common.enums import RuntimeState
from hca.common.types import RunContext

def test_legal_transitions():
    rt = Runtime()
    context = RunContext(goal="test legal")
    # Initial state is created
    rt._current_state = RuntimeState.created
    
    # Test a few legal transitions
    rt._set_state(context, RuntimeState.initializing)
    assert rt._current_state == RuntimeState.initializing
    
    rt._set_state(context, RuntimeState.gathering_inputs)
    assert rt._current_state == RuntimeState.gathering_inputs

def test_illegal_transition_fails():
    rt = Runtime()
    context = RunContext(goal="test illegal")
    rt._current_state = RuntimeState.created
    
    # created -> executing is illegal
    try:
        rt._set_state(context, RuntimeState.executing)
        raise Exception("Should have failed")
    except ValueError as e:
        msg = str(e)
        print(f"Caught expected error: {msg}")
        assert "Illegal state transition" in msg
        assert "created -> executing" in msg
        # Note: state_machine.py uses set(), order may vary
        assert "Allowed transitions from created" in msg
        assert "initializing" in msg
        assert "failed" in msg
        assert "halted" in msg

if __name__ == "__main__":
    test_legal_transitions()
    print("test_legal_transitions passed")
    test_illegal_transition_fails()
    print("test_illegal_transition_fails passed")
