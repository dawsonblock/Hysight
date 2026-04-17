"""HCA API backend tests — self-contained, no external services required."""
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _seed_run(run_id: str, goal: str, *, completed: bool = True):
    from hca.common.enums import EventType, RuntimeState  # type: ignore
    from hca.common.types import RunContext  # type: ignore
    from hca.storage.event_log import append_event  # type: ignore
    from hca.storage.runs import save_run  # type: ignore

    context = RunContext(
        run_id=run_id,
        goal=goal,
        state=(RuntimeState.completed if completed else RuntimeState.created),
    )
    save_run(context)
    append_event(
        context,
        EventType.run_created,
        "runtime",
        {"goal": goal},
    )
    if completed:
        append_event(
            context,
            EventType.run_completed,
            "runtime",
            {"status": "success"},
        )
    return context


def _seed_artifact(run_id: str, artifact_id: str, content: str):
    from hca.paths import (  # type: ignore
        relative_run_storage_path,
        run_storage_path,
    )
    from hca.storage.artifacts import append_artifact  # type: ignore

    artifact_path = run_storage_path(run_id, "artifacts", "report.txt")
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(content, encoding="utf-8")

    append_artifact(
        run_id,
        {
            "artifact_id": artifact_id,
            "run_id": run_id,
            "action_id": "action-1",
            "kind": "create_run_report",
            "path": relative_run_storage_path(
                run_id,
                "artifacts",
                "report.txt",
            ).as_posix(),
            "source_action_ids": ["action-1"],
            "file_paths": [],
            "hashes": {},
            "approval_id": None,
            "workflow_id": None,
            "metadata": {"args": {"note": "seeded artifact"}},
        },
    )


def _key_event_types(summary_payload):
    return [
        event.get("type")
        for event in summary_payload.get("key_events", [])
        if isinstance(event, dict)
    ]


def _parse_sse_events(body: str):
    events = []
    event_name = None
    data_lines = []

    for line in body.splitlines():
        if line.startswith("event: "):
            event_name = line.split(": ", 1)[1]
        elif line.startswith("data: "):
            data_lines.append(line.split(": ", 1)[1])
        elif not line.strip() and event_name is not None:
            payload = json.loads("\n".join(data_lines)) if data_lines else None
            events.append((event_name, payload))
            event_name = None
            data_lines = []

    if event_name is not None:
        payload = json.loads("\n".join(data_lines)) if data_lines else None
        events.append((event_name, payload))

    return events


# Root / health.


def test_root_message(app_client):
    r = app_client.get("/api/")
    assert r.status_code == 200
    assert r.json().get("message") == "HCA API — Hybrid Cognitive Agent"


# HCA run: not found.


def test_get_run_not_found(app_client):
    r = app_client.get("/api/hca/run/nonexistent-run-id")
    assert r.status_code == 404


def test_list_runs_returns_bounded_summaries(app_client):
    first = _seed_run("run-alpha", "alpha goal")
    second = _seed_run("run-beta", "beta goal")
    storage_root = Path(os.environ["HCA_STORAGE_ROOT"])

    os.utime(
        storage_root / "runs" / first.run_id / "run.json",
        (1, 1),
    )
    os.utime(
        storage_root / "runs" / second.run_id / "run.json",
        (2, 2),
    )

    r = app_client.get("/api/hca/runs?limit=10")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 2
    assert [record["run_id"] for record in data["records"]] == [
        "run-beta",
        "run-alpha",
    ]
    assert all(record.get("created_at") for record in data["records"])
    assert all(record.get("updated_at") for record in data["records"])


def test_list_runs_query_filters_by_goal(app_client):
    _seed_run("run-alpha", "alpha goal")
    _seed_run("run-beta", "beta goal")

    r = app_client.get("/api/hca/runs?q=beta")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert [record["run_id"] for record in data["records"]] == ["run-beta"]


def test_get_run_events_returns_newest_first(app_client):
    context = _seed_run("run-events", "eventful goal", completed=False)

    from hca.common.enums import EventType  # type: ignore
    from hca.storage.event_log import append_event  # type: ignore

    append_event(
        context,
        EventType.action_selected,
        "runtime",
        {"kind": "echo", "action_id": "action-1"},
    )
    append_event(
        context,
        EventType.run_completed,
        "runtime",
        {"status": "success"},
    )

    r = app_client.get("/api/hca/run/run-events/events?limit=10")
    assert r.status_code == 200
    data = r.json()
    assert data["run_id"] == "run-events"
    assert data["total"] == 3
    assert data["records"][0]["event_type"] == "run_completed"
    assert data["records"][0]["is_key_event"] is True
    assert data["records"][1]["summary"] == "Selected action: echo"


def test_get_run_artifacts_and_detail(app_client):
    _seed_run("run-artifacts", "artifact goal")
    _seed_artifact("run-artifacts", "artifact-1", "artifact content")

    list_response = app_client.get("/api/hca/run/run-artifacts/artifacts")
    assert list_response.status_code == 200
    data = list_response.json()
    assert data["run_id"] == "run-artifacts"
    assert data["total"] == 1
    assert data["records"][0]["artifact_id"] == "artifact-1"
    assert data["records"][0]["content_available"] is True

    detail_response = app_client.get(
        "/api/hca/run/run-artifacts/artifacts/artifact-1"
    )
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["artifact_id"] == "artifact-1"
    assert detail["content"] == "artifact content"
    assert detail["size_bytes"] == len("artifact content")
    assert detail["truncated"] is False


def test_stream_endpoint_emits_done_event_for_successful_run(app_client):
    response = app_client.post(
        "/api/hca/run/stream",
        json={"goal": "Hello, what can you do?"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith(
        "text/event-stream"
    )

    events = _parse_sse_events(response.text)
    assert events[0][0] == "status"
    assert any(name == "step" for name, _payload in events)
    step_payloads = [
        payload
        for name, payload in events
        if name == "step" and isinstance(payload, dict)
    ]
    event_ids = [payload.get("event_id") for payload in step_payloads]
    assert step_payloads
    assert all(event_ids)
    assert len(set(event_ids)) == len(event_ids)
    assert any(
        name == "step" and payload.get("event_type") == "run_completed"
        for name, payload in events
        if isinstance(payload, dict)
    )

    done_payload = next(
        payload for name, payload in events if name == "done"
    )
    assert done_payload["state"] == "completed"
    assert done_payload["discrepancies"] == []


def test_stream_endpoint_emits_error_event_when_runtime_raises(
    app_client,
    monkeypatch,
):
    from hca.runtime.runtime import Runtime  # type: ignore

    def _boom(self, goal, user_id=None):
        raise RuntimeError("boom")

    monkeypatch.setattr(Runtime, "run", _boom)

    response = app_client.post(
        "/api/hca/run/stream",
        json={"goal": "Hello, what can you do?"},
    )

    assert response.status_code == 200
    events = _parse_sse_events(response.text)
    assert events[0][0] == "status"
    assert any(name == "error" for name, _payload in events)
    assert not any(name == "done" for name, _payload in events)

    error_payload = next(
        payload for name, payload in events if name == "error"
    )
    assert error_payload == {"label": "boom"}


def test_stream_endpoint_emits_done_event_for_halted_run(app_client, monkeypatch):
    from hca.runtime.runtime import Runtime  # type: ignore

    pending_response = app_client.post(
        "/api/hca/run",
        json={"goal": "Please remember that stream denial parity matters"},
    )
    assert pending_response.status_code == 200
    pending = pending_response.json()
    run_id = pending["run_id"]
    approval_id = pending["approval_id"]

    deny_response = app_client.post(
        f"/api/hca/run/{run_id}/deny",
        json={"approval_id": approval_id},
    )
    assert deny_response.status_code == 200
    denied = deny_response.json()
    assert denied["state"] == "halted"

    def _return_halted(self, goal, user_id=None):
        return run_id

    monkeypatch.setattr(Runtime, "run", _return_halted)

    response = app_client.post(
        "/api/hca/run/stream",
        json={"goal": "Please remember that stream denial parity matters"},
    )

    assert response.status_code == 200
    events = _parse_sse_events(response.text)
    done_payload = next(
        payload for name, payload in events if name == "done"
    )
    key_event_types = {
        payload.get("event_type")
        for name, payload in events
        if name == "step" and isinstance(payload, dict)
    }

    assert "approval_denied" in key_event_types
    assert "run_completed" not in key_event_types
    assert done_payload["run_id"] == run_id
    assert done_payload["state"] == "halted"
    assert done_payload["latest_receipt"] is None
    assert done_payload["last_approval_decision"] == "denied"
    assert done_payload["discrepancies"] == []


def test_run_summary_uses_recorded_memory_hits_and_metrics(
    app_client,
    monkeypatch,
):
    from hca.common.enums import (  # type: ignore
        EventType,
        ReceiptStatus,
        RuntimeState,
    )
    from hca.common.types import ExecutionReceipt, RunContext  # type: ignore
    from hca.storage.event_log import append_event  # type: ignore
    from hca.storage.receipts import append_receipt  # type: ignore
    from hca.storage.runs import save_run  # type: ignore

    context = RunContext(
        run_id="run-summary-metrics",
        goal="find the stored API expiry",
        state=RuntimeState.completed,
    )
    save_run(context)
    append_event(
        context,
        EventType.run_created,
        "runtime",
        {"goal": context.goal},
    )
    append_event(
        context,
        EventType.module_proposed,
        "planner",
        {
            "candidate_items": [
                {
                    "kind": "task_plan",
                    "confidence": 0.73,
                    "content": {
                        "strategy": "information_retrieval_strategy",
                        "action": "echo",
                        "rationale": "Rule-based replay proof.",
                        "memory_context_used": True,
                        "planning_mode": "rule_based_fallback",
                        "fallback_reason": "llm_error:RuntimeError",
                        "memory_retrieval_status": "retrieved",
                        "memory_retrieval_error": None,
                        "memory_hits": [
                            {
                                "text": "The API key expires on March 1st.",
                                "score": 0.98,
                                "memory_type": "fact",
                                "stored_at": "2026-03-01T00:00:00+00:00",
                            }
                        ],
                        "memory_retrieval_latency_ms": 4.5,
                    },
                }
            ]
        },
    )
    append_event(
        context,
        EventType.module_proposed,
        "perception_text",
        {
            "candidate_items": [
                {
                    "kind": "perceived_intent",
                    "content": {
                        "intent_class": "retrieve_memory",
                        "intent": "retrieve",
                        "arguments": {"query": context.goal},
                        "perception_mode": "rule_based_fallback",
                        "fallback_reason": "llm_error:RuntimeError",
                        "llm_attempted": True,
                    },
                }
            ]
        },
    )
    append_event(
        context,
        EventType.recurrent_pass_completed,
        "runtime",
        {
            "revision_payloads": [
                {
                    "source_module": "critic",
                    "critique_items": [
                        {
                            "kind": "critic_verdict",
                            "content": {
                                "verdict": "approve",
                                "issues": [],
                                "confidence_delta": 0.02,
                                "rationale": "Replay-backed critic proof.",
                                "llm_powered": False,
                                "fallback_reason": "rule_based_only",
                            },
                        }
                    ],
                }
            ]
        },
    )

    started_at = datetime.now(timezone.utc)
    finished_at = started_at + timedelta(milliseconds=25)
    receipt = ExecutionReceipt(
        action_id="action-1",
        action_kind="echo",
        status=ReceiptStatus.success,
        started_at=started_at,
        finished_at=finished_at,
        outputs={"duration_seconds": 0.025},
    )
    append_receipt(context.run_id, receipt.model_dump(mode="json"))
    append_event(
        context,
        EventType.execution_finished,
        "executor",
        receipt.model_dump(mode="json"),
    )
    append_event(
        context,
        EventType.episodic_memory_written,
        "runtime",
        {
            "action_id": "action-1",
            "subject": "echo",
            "latency_ms": 1.75,
        },
    )
    append_event(
        context,
        EventType.run_completed,
        "runtime",
        {"receipt_id": receipt.receipt_id},
    )

    import memory_service.singleton as _memory_singleton

    def _unexpected_memory_lookup():
        raise AssertionError("run summary performed a live memory lookup")

    monkeypatch.setattr(
        _memory_singleton,
        "get_controller",
        _unexpected_memory_lookup,
        raising=False,
    )

    response = app_client.get(f"/api/hca/run/{context.run_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["plan"]["planning_mode"] == "rule_based_fallback"
    assert data["plan"]["fallback_reason"] == "llm_error:RuntimeError"
    assert data["plan"]["memory_retrieval_status"] == "retrieved"
    assert data["plan"]["memory_retrieval_error"] is None
    assert data["perception"]["intent_class"] == "retrieve_memory"
    assert data["perception"]["intent"] == "retrieve"
    assert data["perception"]["perception_mode"] == "rule_based_fallback"
    assert (
        data["perception"]["fallback_reason"]
        == "llm_error:RuntimeError"
    )
    assert data["perception"]["llm_attempted"] is True
    assert data["critique"]["verdict"] == "approve"
    assert data["critique"]["issues"] == []
    assert data["critique"]["rationale"] == "Replay-backed critic proof."
    assert data["critique"]["llm_powered"] is False
    assert data["critique"]["fallback_reason"] == "rule_based_only"
    assert data["critique"]["confidence_delta"] == 0.02
    assert (
        data["memory_hits"][0]["text"]
        == "The API key expires on March 1st."
    )
    assert data["metrics"]["memory_retrieval_latency"]["count"] == 1
    assert data["metrics"]["memory_retrieval_latency"]["total_ms"] == 4.5
    assert data["metrics"]["tool_latency"]["count"] == 1
    assert data["metrics"]["memory_commit_latency"]["count"] == 1
    assert data["metrics"]["run_duration_ms"] is not None


def test_run_summary_surfaces_workflow_outcome_and_critic_scores(
    app_client,
):
    from hca.common.enums import EventType, RuntimeState  # type: ignore
    from hca.common.types import RunContext  # type: ignore
    from hca.storage.event_log import append_event  # type: ignore
    from hca.storage.runs import save_run  # type: ignore

    context = RunContext(
        run_id="run-workflow-outcome",
        goal="exercise structured workflow outcome",
        state=RuntimeState.failed,
    )
    save_run(context)
    append_event(
        context,
        EventType.run_created,
        "runtime",
        {"goal": context.goal},
    )
    append_event(
        context,
        EventType.recurrent_pass_completed,
        "runtime",
        {
            "revision_payloads": [
                {
                    "source_module": "critic",
                    "critique_items": [
                        {
                            "kind": "critic_verdict",
                            "content": {
                                "verdict": "revise",
                                "alignment": 0.61,
                                "feasibility": 0.72,
                                "safety": 0.94,
                                "issues": ["Need one more verification step"],
                                "confidence_delta": -0.03,
                                "rationale": (
                                    "Budget exhausted before verification."
                                ),
                                "llm_powered": False,
                                "fallback_reason": "rule_based_only",
                            },
                        }
                    ],
                }
            ]
        },
    )
    append_event(
        context,
        EventType.workflow_budget_exhausted,
        "runtime",
        {
            "workflow_id": "workflow-1",
            "max_steps": 1,
            "consumed_steps": 1,
            "next_step_id": "step-2",
        },
    )
    append_event(
        context,
        EventType.workflow_terminated,
        "runtime",
        {
            "workflow_id": "workflow-1",
            "reason": "budget_exhausted",
            "consumed_steps": 1,
            "next_step_id": "step-2",
        },
    )

    response = app_client.get(f"/api/hca/run/{context.run_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["workflow_outcome"] == {
        "terminal_event": "workflow_terminated",
        "reason": "budget_exhausted",
        "workflow_step_id": None,
        "next_step_id": "step-2",
    }
    assert data["critique"]["verdict"] == "revise"
    assert data["critique"]["alignment"] == 0.61
    assert data["critique"]["feasibility"] == 0.72
    assert data["critique"]["safety"] == 0.94
    assert data["critique"]["issues"] == [
        "Need one more verification step"
    ]
    assert data["critique"]["confidence_delta"] == -0.03
    assert data["critique"]["fallback_reason"] == "rule_based_only"


def test_memory_retrieval_failure_is_explicit_but_nonfatal(
    app_client,
    monkeypatch,
):
    import memory_service.singleton as memory_singleton

    def _fail_controller_lookup():
        raise RuntimeError("memory offline")

    monkeypatch.setattr(
        memory_singleton,
        "get_controller",
        _fail_controller_lookup,
    )

    response = app_client.post(
        "/api/hca/run",
        json={"goal": "What facts are stored in memory?"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["state"] == "completed"
    assert data["plan"]["memory_retrieval_status"] == "failed"
    assert data["plan"]["memory_retrieval_error"] == "RuntimeError"
    assert data["discrepancies"] == []

    key_event_types = _key_event_types(data)
    assert "run_completed" in key_event_types
    assert "run_failed" not in key_event_types


def test_approve_rejects_non_pending_approval_without_writing_grant(
    app_client,
):
    from hca.common.enums import ActionClass, RuntimeState  # type: ignore
    from hca.common.types import ApprovalRequest, RunContext  # type: ignore
    from hca.storage.approvals import (  # type: ignore
        append_request,
        iter_records,
    )
    from hca.storage.runs import save_run  # type: ignore

    context = RunContext(
        run_id="run-approval-mismatch",
        goal="remember this",
        state=RuntimeState.awaiting_approval,
        pending_approval_id="approval-expected",
    )
    save_run(context)
    append_request(
        context.run_id,
        ApprovalRequest(
            approval_id="approval-expected",
            run_id=context.run_id,
            action_id="action-1",
            action_kind="store_note",
            action_class=ActionClass.medium,
            reason="Action requires approval",
        ),
    )

    response = app_client.post(
        f"/api/hca/run/{context.run_id}/approve",
        json={"approval_id": "approval-other"},
    )
    assert response.status_code == 400
    assert (
        response.json()["detail"]
        == "Approval id does not match pending approval"
    )
    records = list(iter_records(context.run_id))
    assert [record["record_type"] for record in records] == ["request"]


def test_deny_rejects_non_pending_approval(app_client):
    from hca.common.enums import ActionClass, RuntimeState  # type: ignore
    from hca.common.types import ApprovalRequest, RunContext  # type: ignore
    from hca.storage.approvals import (  # type: ignore
        append_request,
        iter_records,
    )
    from hca.storage.runs import save_run  # type: ignore

    context = RunContext(
        run_id="run-deny-mismatch",
        goal="remember this too",
        state=RuntimeState.awaiting_approval,
        pending_approval_id="approval-expected",
    )
    save_run(context)
    append_request(
        context.run_id,
        ApprovalRequest(
            approval_id="approval-expected",
            run_id=context.run_id,
            action_id="action-1",
            action_kind="store_note",
            action_class=ActionClass.medium,
            reason="Action requires approval",
        ),
    )

    response = app_client.post(
        f"/api/hca/run/{context.run_id}/deny",
        json={"approval_id": "approval-other"},
    )
    assert response.status_code == 400
    assert (
        response.json()["detail"]
        == "Approval id does not match pending approval"
    )
    records = list(iter_records(context.run_id))
    assert [record["record_type"] for record in records] == ["request"]


# Memory retrieve: empty store returns empty hits.


def test_memory_retrieve_returns_hits_array(app_client):
    r = app_client.post(
        "/api/hca/memory/retrieve",
        json={"query_text": "hello", "top_k": 5},
    )
    assert r.status_code == 200
    data = r.json()
    assert "hits" in data
    assert isinstance(data["hits"], list)


def test_memory_retrieve_rejects_legacy_query_wrapper(app_client):
    r = app_client.post("/api/hca/memory/retrieve", json={"query": "hello"})
    assert r.status_code == 422


def test_memory_retrieve_rejects_blank_query_text(app_client):
    r = app_client.post(
        "/api/hca/memory/retrieve",
        json={"query_text": "", "top_k": 5},
    )
    assert r.status_code == 422


def test_memory_retrieve_hit_shape(app_client):
    """Seed one record and pin the exact shape of a retrieve hit."""
    from memory_service.singleton import get_controller
    from memory_service import CandidateMemory

    get_controller().ingest(
        CandidateMemory(raw_text="the sky is blue today", memory_type="fact")
    )
    r = app_client.post(
        "/api/hca/memory/retrieve",
        json={"query_text": "sky blue", "top_k": 5},
    )
    assert r.status_code == 200
    hits = r.json()["hits"]
    assert len(hits) >= 1
    hit = hits[0]
    expected_keys = {
        "memory_id",
        "belief_id",
        "memory_layer",
        "memory_type",
        "entity",
        "slot",
        "value",
        "text",
        "score",
        "confidence",
        "stored_at",
        "expired",
        "metadata",
    }
    assert expected_keys.issubset(hit.keys())
    assert isinstance(hit["text"], str)
    assert isinstance(hit["score"], float)
    assert hit["score"] > 0
    assert isinstance(hit["memory_type"], str)
    assert isinstance(hit["memory_id"], str)
    assert hit["memory_layer"] == "trace"
    assert isinstance(hit["confidence"], float)
    assert hit["stored_at"] is not None
    assert hit["expired"] is False
    assert isinstance(hit["metadata"], dict)
    assert "raw_text" not in hit


def test_memory_maintain_envelope(app_client):
    """Pin the maintenance report response envelope."""
    r = app_client.post("/api/hca/memory/maintain")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data["durable_memory_count"], int)
    assert isinstance(data["expired_count"], int)
    assert isinstance(data["expired_ids"], list)
    assert isinstance(data["compaction_supported"], bool)
    assert isinstance(data["compactor_status"], str)


# Full HCA run.

@pytest.mark.slow
def test_basic_run_completed(app_client):
    r = app_client.post(
        "/api/hca/run",
        json={"goal": "Hello, what can you do?"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data.get("state") == "completed"
    assert data.get("plan", {}).get("strategy") is not None
    assert data.get("plan", {}).get("action") is not None
    assert data.get("approval_id") is None
    assert data.get("last_approval_decision") is None
    assert data.get("action_taken", {}).get("kind") is not None
    assert data.get("action_taken", {}).get("action_id") is not None
    assert data.get("action_taken", {}).get("requires_approval") is False
    assert data.get("action_result", {}).get("status") == "success"
    assert data.get("latest_receipt", {}).get("status") == "success"
    assert (
        data.get("latest_receipt", {}).get("action_id")
        == data.get("action_taken", {}).get("action_id")
    )
    assert isinstance(data.get("artifacts"), list)
    assert data.get("artifacts_count") == len(data.get("artifacts", []))
    assert isinstance(data.get("memory_counts"), dict)
    assert isinstance(data.get("memory_outcomes"), dict)
    assert data.get("discrepancies") == []
    assert data.get("plan", {}).get("planning_mode") is not None
    assert "fallback_reason" in data.get("plan", {})
    assert "memory_retrieval_status" in data.get("plan", {})
    assert "memory_retrieval_error" in data.get("plan", {})
    assert isinstance(data.get("perception"), dict)
    assert "perception_mode" in data.get("perception", {})
    assert "fallback_reason" in data.get("perception", {})
    assert "llm_attempted" in data.get("perception", {})
    assert isinstance(data.get("critique"), dict)
    assert "alignment" in data.get("critique", {})
    assert "feasibility" in data.get("critique", {})
    assert "safety" in data.get("critique", {})
    assert "llm_powered" in data.get("critique", {})
    assert "fallback_reason" in data.get("critique", {})
    assert isinstance(data.get("workflow_outcome"), dict)
    assert "terminal_event" in data.get("workflow_outcome", {})
    assert "reason" in data.get("workflow_outcome", {})
    assert isinstance(data.get("metrics"), dict)
    assert data.get("event_count", 0) > 0

    key_event_types = _key_event_types(data)
    assert "action_selected" in key_event_types
    assert "execution_finished" in key_event_types
    assert "run_completed" in key_event_types
    assert "approval_requested" not in key_event_types
    assert "run_failed" not in key_event_types


@pytest.mark.slow
def test_get_run_by_id(app_client):
    r = app_client.post(
        "/api/hca/run",
        json={"goal": "Hello, what can you do?"},
    )
    assert r.status_code == 200
    run_id = r.json().get("run_id")
    assert run_id

    r2 = app_client.get(f"/api/hca/run/{run_id}")
    assert r2.status_code == 200
    data = r2.json()
    assert data.get("run_id") == run_id
    assert "state" in data
    assert "key_events" in data
    assert "latest_receipt" in data
    assert "workflow_step_history" in data


@pytest.mark.slow
def test_contract_run_includes_replay_workflow_fields(app_client):
    r = app_client.post(
        "/api/hca/run",
        json={
            "goal": (
                "investigate contract mismatch for `RuntimeState` in "
                "`hca/src/hca/common/enums.py`"
            )
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data.get("state") == "completed"
    assert data.get("active_workflow", {}).get("workflow_class") == (
        "contract_api_drift"
    )
    assert data.get("active_workflow", {}).get("strategy") == (
        "contract_drift_strategy"
    )
    assert data.get("workflow_budget", {}).get("max_steps") == 7
    assert [
        step.get("step_key")
        for step in data.get("workflow_step_history", [])
    ] == [
        "target_glob",
        "target_search",
        "target_read_context",
        "contract_surface_search",
        "contract_surface_read_context",
        "contract_surface_summary",
        "run_report",
    ]
    assert any(
        "contract_drift_summary" in artifact.get("path", "")
        for artifact in data.get("workflow_artifacts", [])
    )
    assert data.get("discrepancies") == []


@pytest.mark.slow
def test_runtime_memory_question_returns_summary(app_client):
    r = app_client.post(
        "/api/hca/run",
        json={"goal": "What facts are stored in memory?"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data.get("run_id")
    assert "state" in data


@pytest.mark.slow
def test_runtime_memory_recall_response_not_empty(app_client):
    r = app_client.post(
        "/api/hca/run",
        json={"goal": "Test memory recall"},
    )
    assert r.status_code == 200
    assert r.json()


# HCA approval flow.

@pytest.mark.slow
def test_remember_goal_awaiting_approval(app_client):
    r = app_client.post(
        "/api/hca/run",
        json={"goal": "Please remember that testing was done on Feb 2026"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data.get("state") == "awaiting_approval"
    assert data.get("approval_id") is not None
    assert data.get("last_approval_decision") is None
    assert data.get("action_taken", {}).get("kind") == "store_note"
    assert data.get("action_taken", {}).get("requires_approval") is True
    assert data.get("latest_receipt") is None
    assert data.get("discrepancies") == []

    key_event_types = _key_event_types(data)
    assert "action_selected" in key_event_types
    assert "approval_requested" in key_event_types
    assert "execution_finished" not in key_event_types
    assert "run_completed" not in key_event_types
    assert "run_failed" not in key_event_types


@pytest.mark.slow
def test_approve_action_completes(app_client):
    r = app_client.post(
        "/api/hca/run",
        json={"goal": "Please remember that testing was done on Feb 2026"},
    )
    assert r.status_code == 200
    data = r.json()
    run_id = data.get("run_id")
    approval_id = data.get("approval_id")
    assert data.get("state") == "awaiting_approval"
    assert approval_id is not None

    r2 = app_client.post(
        f"/api/hca/run/{run_id}/approve",
        json={"approval_id": approval_id},
    )
    assert r2.status_code == 200
    approved = r2.json()
    assert approved.get("state") == "completed"
    assert approved.get("approval_id") == approval_id
    assert approved.get("last_approval_decision") == "granted"
    assert approved.get("latest_receipt", {}).get("status") == "success"
    assert approved.get("discrepancies") == []
    assert approved.get("action_taken", {}).get("kind") == "store_note"
    assert approved.get("memory_outcomes", {}).get("episodic_memory_writes", 0) >= 1

    key_event_types = _key_event_types(approved)
    assert "approval_requested" in key_event_types
    assert "approval_granted" in key_event_types
    assert "execution_finished" in key_event_types
    assert "run_completed" in key_event_types
    assert "run_failed" not in key_event_types


@pytest.mark.slow
def test_deny_action_halts_without_execution(app_client):
    r = app_client.post(
        "/api/hca/run",
        json={"goal": "Please remember that testing was done on Feb 2026"},
    )
    assert r.status_code == 200
    pending = r.json()
    run_id = pending.get("run_id")
    approval_id = pending.get("approval_id")
    assert pending.get("state") == "awaiting_approval"
    assert approval_id is not None

    denied_response = app_client.post(
        f"/api/hca/run/{run_id}/deny",
        json={"approval_id": approval_id},
    )
    assert denied_response.status_code == 200

    denied = denied_response.json()
    assert denied.get("state") == "halted"
    assert denied.get("approval_id") == approval_id
    assert denied.get("last_approval_decision") == "denied"
    assert denied.get("latest_receipt") is None
    assert denied.get("discrepancies") == []

    key_event_types = _key_event_types(denied)
    assert "approval_requested" in key_event_types
    assert "approval_denied" in key_event_types
    assert "execution_finished" not in key_event_types
    assert "run_completed" not in key_event_types
    assert "run_failed" not in key_event_types


@pytest.mark.slow
def test_approve_action_recovers_from_stale_run_context(app_client):
    from hca.common.enums import RuntimeState  # type: ignore
    from hca.storage.runs import load_run, save_run  # type: ignore

    response = app_client.post(
        "/api/hca/run",
        json={"goal": "Please remember that approvals need recovery tests"},
    )
    assert response.status_code == 200
    pending = response.json()
    run_id = pending["run_id"]
    approval_id = pending["approval_id"]

    context = load_run(run_id)
    assert context is not None
    context.state = RuntimeState.completed
    context.pending_approval_id = None
    save_run(context)

    approval_response = app_client.post(
        f"/api/hca/run/{run_id}/approve",
        json={"approval_id": approval_id},
    )
    assert approval_response.status_code == 200
    approved = approval_response.json()
    assert approved["state"] == "completed"
    assert approved["approval_id"] == approval_id
    assert approved["last_approval_decision"] == "granted"
    assert approved["discrepancies"] == []


@pytest.mark.slow
def test_approve_rejects_when_context_is_stale_but_replay_is_terminal(
    app_client,
):
    from hca.common.enums import RuntimeState  # type: ignore
    from hca.storage.runs import load_run, save_run  # type: ignore

    response = app_client.post(
        "/api/hca/run",
        json={"goal": "Please remember that replay should stay authoritative"},
    )
    assert response.status_code == 200
    pending = response.json()
    run_id = pending["run_id"]
    approval_id = pending["approval_id"]

    denied_response = app_client.post(
        f"/api/hca/run/{run_id}/deny",
        json={"approval_id": approval_id},
    )
    assert denied_response.status_code == 200
    assert denied_response.json()["state"] == "halted"

    context = load_run(run_id)
    assert context is not None
    context.state = RuntimeState.awaiting_approval
    context.pending_approval_id = approval_id
    save_run(context)

    approval_response = app_client.post(
        f"/api/hca/run/{run_id}/approve",
        json={"approval_id": approval_id},
    )
    assert approval_response.status_code == 400
    assert approval_response.json()["detail"] == "Run has no pending approval"


# Status endpoints.


def test_status_route_returns_503_without_db(app_client):
    """app_client deletes MONGO_URL so the status route must return 503."""
    r = app_client.post("/api/status", json={"client_name": "test"})
    assert r.status_code == 503


def test_subsystems_route_surfaces_mode_and_optional_status(app_client):
    response = app_client.get("/api/subsystems")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert data["database"]["status"] == "disabled"
    assert data["memory"]["backend"] == "python"
    assert data["memory"]["status"] == "healthy"
    assert data["storage"]["status"] == "writable"
    assert data["llm"]["status"] == "missing"
