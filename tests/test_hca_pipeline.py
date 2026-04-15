"""Integration test for the full HCA pipeline.

Run from the repository root with:
    python -m pytest tests/test_hca_pipeline.py -v
    # or directly:
    python tests/test_hca_pipeline.py
"""

import sys
from importlib import import_module
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

memory_service = import_module("memory_service")
memory_controller_module = import_module("memory_service.controller")
CandidateMemory = memory_service.CandidateMemory
RetrievalQuery = memory_service.RetrievalQuery
MemoryController = memory_controller_module.MemoryController


def _event_types_for_run(run_id):
    from hca.storage import iter_events

    return [event["event_type"] for event in iter_events(run_id)]


# Memory service tests.

class TestMemoryController:
    def setup_method(self):
        self.ctrl = MemoryController()  # in-memory, no disk

    def test_ingest_returns_id(self):
        mid = self.ctrl.ingest(
            CandidateMemory(
                raw_text="The API key for production expires on March 1st.",
                memory_type="fact",
            )
        )
        assert mid is not None
        assert isinstance(mid, str)

    def test_retrieve_bm25(self):
        self.ctrl.ingest(
            CandidateMemory(
                raw_text="The API key expires March 1st",
                memory_type="fact",
            )
        )
        self.ctrl.ingest(
            CandidateMemory(
                raw_text="Deploy the new service to production",
                memory_type="episode",
            )
        )

        hits = self.ctrl.retrieve(
            RetrievalQuery(query_text="API key expiry", top_k=5)
        )
        assert len(hits) >= 1
        assert "API" in hits[0].text or "expires" in hits[0].text

    def test_retrieve_empty(self):
        hits = self.ctrl.retrieve(
            RetrievalQuery(
                query_text="something completely unrelated zzz"
            )
        )
        assert hits == []

    def test_maintain_no_expiry(self):
        self.ctrl.ingest(
            CandidateMemory(raw_text="recent memory", memory_type="trace")
        )
        report = self.ctrl.maintain()
        assert report.expired_count == 0
        assert isinstance(report.durable_memory_count, int)


# HCA runtime tests.

class TestHCARuntimeSmoke:
    def test_echo_run_completes(self):
        """Simplest possible run — should complete without approval."""
        from hca.runtime.runtime import Runtime
        from hca.storage import load_run

        rt = Runtime()
        run_id = rt.run("Hello, what can you do?")
        assert run_id is not None

        ctx = load_run(run_id)
        assert ctx is not None
        assert ctx.state.value == "completed"

        event_types = _event_types_for_run(run_id)
        assert event_types[0] == "run_created"
        assert "execution_finished" in event_types
        assert "run_completed" in event_types
        assert "run_failed" not in event_types

    def test_run_creates_events(self):
        """Every non-approval smoke run should produce a healthy trace."""
        from hca.runtime.runtime import Runtime

        rt = Runtime()
        run_id = rt.run("Echo hello please")
        event_types = _event_types_for_run(run_id)

        assert len(event_types) > 0
        assert "run_created" in event_types
        assert "action_selected" in event_types
        assert "execution_finished" in event_types
        assert "run_completed" in event_types
        assert "run_failed" not in event_types

    def test_store_goal_produces_approval(self):
        """A 'remember' goal should trigger approval flow."""
        from hca.runtime.runtime import Runtime
        from hca.storage import load_run
        from hca.storage.approvals import get_pending_requests

        rt = Runtime()
        run_id = rt.run("Remember that the sprint ends on Friday")
        ctx = load_run(run_id)
        assert ctx is not None
        assert ctx.state.value == "awaiting_approval"

        pending_requests = get_pending_requests(run_id)
        assert len(pending_requests) == 1
        assert pending_requests[0].action_kind == "store_note"

        event_types = _event_types_for_run(run_id)
        assert event_types[0] == "run_created"
        assert "action_selected" in event_types
        assert "approval_requested" in event_types
        assert "execution_finished" not in event_types
        assert "run_completed" not in event_types
        assert "run_failed" not in event_types


# Direct run.

if __name__ == "__main__":
    print("=== Memory Service Tests ===")
    t = TestMemoryController()
    t.setup_method()

    print("[1] ingest returns id …", end=" ")
    t.test_ingest_returns_id()
    print("OK")

    t.setup_method()
    print("[2] retrieve BM25 …", end=" ")
    t.test_retrieve_bm25()
    print("OK")

    t.setup_method()
    print("[3] retrieve empty …", end=" ")
    t.test_retrieve_empty()
    print("OK")

    t.setup_method()
    print("[4] maintain …", end=" ")
    t.test_maintain_no_expiry()
    print("OK")

    print("\n=== HCA Runtime Tests ===")
    r = TestHCARuntimeSmoke()
    print("[5] echo run completes …", end=" ")
    r.test_echo_run_completes()
    print("OK")

    print("[6] run creates events …", end=" ")
    r.test_run_creates_events()
    print("OK")

    print("[7] store goal produces approval or completes …", end=" ")
    r.test_store_goal_produces_approval()
    print("OK")

    print("\nAll tests passed.")
