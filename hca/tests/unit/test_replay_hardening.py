from pathlib import Path

from hca.common.enums import ApprovalDecision, EventType, RuntimeState
from hca.runtime.replay import reconstruct_state
from hca.runtime.runtime import Runtime
from hca.storage.approvals import get_pending_requests
from hca.storage.event_log import append_event, read_events
from hca.storage.runs import load_run


def test_replay_after_deny(monkeypatch, tmp_path):
    monkeypatch.setenv("HCA_STORAGE_ROOT", str(tmp_path / "storage"))

    rt = Runtime()
    run_id = rt.run("remember something")

    pending = get_pending_requests(run_id)
    approval_id = pending[0].approval_id

    from hca.storage.approvals import append_denial

    append_denial(run_id, approval_id, reason="User test")

    rt.resume(run_id, approval_id, "no-token")

    state = reconstruct_state(run_id)
    assert state["state"] == RuntimeState.halted.value
    assert state["last_approval_decision"] == ApprovalDecision.denied.value
    assert state["pending_approval_id"] == approval_id


def test_replay_after_completion(monkeypatch, tmp_path):
    monkeypatch.setenv("HCA_STORAGE_ROOT", str(tmp_path / "storage"))

    rt = Runtime()
    run_id = rt.run("echo hello")

    state = reconstruct_state(run_id)
    assert state["state"] == RuntimeState.completed.value
    assert state["selected_action_kind"] == "echo"
    assert state["latest_receipt_id"] is not None
    assert state["memory_counts"]["episodic"] >= 1


def test_replay_ignores_truncated_final_event_line(monkeypatch, tmp_path):
    monkeypatch.setenv("HCA_STORAGE_ROOT", str(tmp_path / "storage"))

    rt = Runtime()
    run_id = rt.run("echo hello")
    events_path = Path(tmp_path / "storage" / "runs" / run_id / "events.jsonl")
    valid_size = events_path.stat().st_size

    with open(events_path, "ab") as handle:
        handle.write(b'{"event_id":"truncated"')

    events, next_offset = read_events(run_id)

    assert next_offset == valid_size
    assert EventType.run_completed.value in [
        event["event_type"] for event in events
    ]
    assert reconstruct_state(run_id)["state"] == RuntimeState.completed.value


def test_read_events_resumes_from_cursor(monkeypatch, tmp_path):
    monkeypatch.setenv("HCA_STORAGE_ROOT", str(tmp_path / "storage"))

    rt = Runtime()
    run_id = rt.run("echo hello")

    initial_events, cursor = read_events(run_id)
    assert initial_events

    empty_events, same_cursor = read_events(run_id, offset=cursor)
    assert empty_events == []
    assert same_cursor == cursor

    context = load_run(run_id)
    assert context is not None
    append_event(
        context,
        EventType.report_emitted,
        "runtime",
        {"reason": "tail"},
    )

    tail_events, next_cursor = read_events(run_id, offset=cursor)
    assert [event["event_type"] for event in tail_events] == [
        EventType.report_emitted.value
    ]
    assert next_cursor > cursor
