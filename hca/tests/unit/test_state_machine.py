import pytest

from hca.common.enums import RuntimeState
from hca.runtime.state_machine import can_transition, assert_transition


def test_valid_transitions():
    assert can_transition(RuntimeState.created, RuntimeState.initializing)
    assert can_transition(RuntimeState.proposing, RuntimeState.admitting)
    assert can_transition(RuntimeState.action_selection, RuntimeState.executing)
    assert can_transition(RuntimeState.action_selection, RuntimeState.awaiting_approval)
    assert can_transition(RuntimeState.executing, RuntimeState.observing)


def test_invalid_transition_raises():
    with pytest.raises(ValueError):
        assert_transition(RuntimeState.created, RuntimeState.executing)