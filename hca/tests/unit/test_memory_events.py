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

    replay = reconstruct_state(run_id)
    assert replay["memory_outcomes"]["episodic_memory_writes"] == 1
    assert replay["memory_outcomes"]["external_memory_writes"] == 1
    assert replay["memory_outcomes"]["external_memory_failures"] == 0


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
    assert (
        failure_events[0]["payload"]["error"]
        == "memory sidecar unavailable"
    )
