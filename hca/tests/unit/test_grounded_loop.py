from hca.runtime.runtime import Runtime
from hca.storage.event_log import iter_events
from hca.common.enums import EventType, RuntimeState


def test_grounded_perception_and_reasoning():
    rt = Runtime()

    # Test case 1: Note storage
    run_id = rt.run("remember to buy milk")
    events = list(iter_events(run_id))

    # Check states
    states = [
        e["next_state"]
        for e in events
        if e["event_type"] == EventType.state_transition.value
    ]
    print(f"States: {states}")

    if RuntimeState.awaiting_approval.value in states:
        print("Run paused for approval as expected.")
        approval_event = [
            e
            for e in events
            if e["event_type"] == EventType.approval_requested.value
        ][0]
        approval_id = approval_event["payload"]["approval_id"]

        from hca.storage.approvals import append_grant
        from hca.common.types import ApprovalGrant

        token = "test-token"
        grant = ApprovalGrant(approval_id=approval_id, token=token)
        append_grant(run_id, grant)

        rt.resume(run_id, approval_id, token)

        events = list(iter_events(run_id))
        states = [
            e["next_state"]
            for e in events
            if e["event_type"] == EventType.state_transition.value
        ]
        print(f"States after resume: {states}")
        assert RuntimeState.completed.value in states

    selected = [
        e
        for e in events
        if e["event_type"] == EventType.action_selected.value
    ][0]
    assert selected["payload"]["kind"] == "store_note"

    started = [
        e
        for e in events
        if e["event_type"] == EventType.execution_started.value
    ][0]
    assert started["payload"]["tool"] == "store_note"
    assert "buy milk" in str(started["payload"]["arguments"])


if __name__ == "__main__":
    test_grounded_perception_and_reasoning()
    print("test_grounded_perception_and_reasoning passed")
