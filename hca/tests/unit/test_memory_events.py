# mypy: ignore-errors
# pyright: reportMissingImports=false, reportMissingTypeStubs=false

from hca.runtime.replay import reconstruct_state
from hca.runtime.runtime import Runtime
from hca.storage.event_log import iter_events

import hca.runtime.runtime as runtime_module


class _FakeCandidateMemory:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class _FakeProvenance:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


def test_runtime_emits_explicit_memory_success_events(monkeypatch, tmp_path):
    monkeypatch.setenv("HCA_STORAGE_ROOT", str(tmp_path / "storage"))

    runtime = Runtime()
    run_id = runtime.run("echo hello")

    event_types = [event["event_type"] for event in iter_events(run_id)]
    assert "episodic_memory_written" in event_types
    assert "external_memory_written" in event_types

    events = list(iter_events(run_id))
    episodic_event = next(
        event
        for event in events
        if event["event_type"] == "episodic_memory_written"
    )
    external_event = next(
        event
        for event in events
        if event["event_type"] == "external_memory_written"
    )
    assert episodic_event["payload"]["run_id"] == run_id
    assert episodic_event["payload"]["sink"] == "episodic_store"
    assert episodic_event["payload"]["status"] == "written"
    assert episodic_event["payload"]["failure_class"] is None
    assert episodic_event["payload"]["finalization_context"] == (
        "single_action"
    )
    assert external_event["payload"]["run_id"] == run_id
    assert external_event["payload"]["sink"] == "external_memory"
    assert external_event["payload"]["status"] == "written"
    assert external_event["payload"]["failure_class"] is None

    replay = reconstruct_state(run_id)
    assert replay["memory_outcomes"]["episodic_memory_writes"] == 1
    assert replay["memory_outcomes"]["external_memory_writes"] == 1
    assert replay["memory_outcomes"]["external_memory_failures"] == 0
    assert replay["memory_outcomes"]["episodic_memory_details"][0][
        "sink"
    ] == "episodic_store"
    assert replay["memory_outcomes"]["external_memory_details"][0][
        "sink"
    ] == "external_memory"


def test_runtime_emits_external_memory_failure_event(monkeypatch, tmp_path):
    monkeypatch.setenv("HCA_STORAGE_ROOT", str(tmp_path / "storage"))

    class _FailingController:
        def ingest(self, candidate):
            raise RuntimeError("memory sidecar unavailable")

    monkeypatch.setattr(
        runtime_module,
        "_load_memory_service_bindings",
        lambda: (
            lambda: _FailingController(),
            _FakeCandidateMemory,
            _FakeProvenance,
        ),
    )

    runtime = Runtime()
    run_id = runtime.run("echo hello")

    replay = reconstruct_state(run_id)
    assert replay["state"] == "completed"
    assert replay["memory_outcomes"]["episodic_memory_writes"] == 1
    assert replay["memory_outcomes"]["external_memory_writes"] == 0
    assert replay["memory_outcomes"]["external_memory_failures"] == 1

    failure_events = [
        event
        for event in iter_events(run_id)
        if event["event_type"] == "external_memory_write_failed"
    ]
    assert len(failure_events) == 1
    assert failure_events[0]["payload"]["run_id"] == run_id
    assert failure_events[0]["payload"]["sink"] == "external_memory"
    assert failure_events[0]["payload"]["status"] == "failed"
    assert failure_events[0]["payload"]["failure_class"] == "RuntimeError"
    assert (
        failure_events[0]["payload"]["error"]
        == "memory sidecar unavailable"
    )
    assert replay["memory_outcomes"]["external_memory_failure_details"][0][
        "status"
    ] == "failed"


def test_runtime_fails_closed_when_memory_commit_raises(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("HCA_STORAGE_ROOT", str(tmp_path / "storage"))

    def _boom(self, context, candidate, receipt_payload):
        raise RuntimeError("memory disk full")

    monkeypatch.setattr(Runtime, "_record_execution_memory", _boom)

    runtime = Runtime()
    run_id = runtime.run("echo hello")

    replay = reconstruct_state(run_id)
    assert replay["state"] == "failed"

    failure_event = next(
        event
        for event in iter_events(run_id)
        if event["event_type"] == "run_failed"
    )
    assert failure_event["payload"]["reason"] == "memory_commit_failed"
    assert failure_event["payload"]["error"] == "memory disk full"
