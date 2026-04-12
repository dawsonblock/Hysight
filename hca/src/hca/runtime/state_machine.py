"""State machine for the hybrid cognitive agent runtime."""

from typing import Dict, Set

from hca.common.enums import RuntimeState


# Define allowed transitions for each state
_TRANSITIONS: Dict[RuntimeState, Set[RuntimeState]] = {
    RuntimeState.created: {RuntimeState.initializing},
    RuntimeState.initializing: {RuntimeState.gathering_inputs},
    RuntimeState.gathering_inputs: {RuntimeState.proposing},
    RuntimeState.proposing: {RuntimeState.admitting},
    RuntimeState.admitting: {RuntimeState.broadcasting},
    RuntimeState.broadcasting: {RuntimeState.recurrent_update},
    RuntimeState.recurrent_update: {RuntimeState.action_selection},
    RuntimeState.action_selection: {
        RuntimeState.awaiting_approval,
        RuntimeState.executing,
        RuntimeState.reporting,
        RuntimeState.proposing,
    },
    RuntimeState.awaiting_approval: {
        RuntimeState.executing,
        RuntimeState.halted,
    },
    RuntimeState.executing: {RuntimeState.observing},
    RuntimeState.observing: {RuntimeState.memory_commit},
    RuntimeState.memory_commit: {
        RuntimeState.proposing,
        RuntimeState.awaiting_approval,
        RuntimeState.executing,
        RuntimeState.reporting,
    },
    RuntimeState.reporting: {RuntimeState.completed},
    RuntimeState.completed: set(),
    RuntimeState.failed: set(),
    RuntimeState.halted: set(),
}


def can_transition(current: RuntimeState, target: RuntimeState) -> bool:
    """Return True if a state transition is allowed."""
    # Any active state can transition to failed or halted
    if target in {RuntimeState.failed, RuntimeState.halted}:
        return current not in {
            RuntimeState.completed,
            RuntimeState.failed,
            RuntimeState.halted,
        }
    allowed = _TRANSITIONS.get(current)
    return allowed is not None and target in allowed


def assert_transition(current: RuntimeState, target: RuntimeState) -> None:
    """Raise an exception if the transition is not allowed."""
    if not can_transition(current, target):
        allowed = _TRANSITIONS.get(current, set())
        # Add the common states allowed from any active state
        if current not in {
            RuntimeState.completed,
            RuntimeState.failed,
            RuntimeState.halted,
        }:
            allowed = allowed.union({RuntimeState.failed, RuntimeState.halted})
        allowed_names = ", ".join(s.value for s in allowed)
        raise ValueError(
            f"Illegal state transition: {current.value} -> {target.value}. "
            f"Allowed transitions from {current.value}: [{allowed_names}]"
        )
