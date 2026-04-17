# mypy: ignore-errors
# pyright: reportMissingImports=false, reportMissingTypeStubs=false

from importlib import import_module
from pathlib import Path

import pytest

critic_module = import_module("hca.modules.critic")
common_types = import_module("hca.common.types")
common_enums = import_module("hca.common.enums")
event_log_module = import_module("hca.storage.event_log")
planner_module = import_module("hca.modules.planner")
replay_module = import_module("hca.runtime.replay")
runtime_module = import_module("hca.runtime.runtime")
tool_reasoner_module = import_module("hca.modules.tool_reasoner")
broadcast_module = import_module("hca.workspace.broadcast")
workspace_module = import_module("hca.workspace.workspace")
approvals_module = import_module("hca.storage.approvals")

RunContext = common_types.RunContext
WorkflowPlan = common_types.WorkflowPlan
WorkflowStep = common_types.WorkflowStep
RuntimeState = common_enums.RuntimeState
WorkflowClass = common_enums.WorkflowClass
WorkspaceItem = common_types.WorkspaceItem
ApprovalGrant = common_types.ApprovalGrant
Critic = critic_module.Critic
Runtime = runtime_module.Runtime
reconstruct_state = replay_module.reconstruct_state
broadcast = broadcast_module.broadcast
iter_events = event_log_module.iter_events
Workspace = workspace_module.Workspace
append_grant = approvals_module.append_grant
get_pending_requests = approvals_module.get_pending_requests


def _stub_workflow_plan(monkeypatch, workflow_plan: WorkflowPlan) -> None:
    def _build(_goal: str) -> WorkflowPlan:
        return workflow_plan.model_copy(deep=True)

    monkeypatch.setattr(planner_module, "build_workflow_plan", _build)
    monkeypatch.setattr(tool_reasoner_module, "build_workflow_plan", _build)


def test_run_completes():
    runtime = Runtime()
    run_id = runtime.run("echo greeting")
    assert isinstance(run_id, str)


def test_run_lists_repo_root(monkeypatch, tmp_path):
    monkeypatch.setenv("HCA_STORAGE_ROOT", str(tmp_path / "storage"))

    runtime = Runtime()
    run_id = runtime.run("list files in the repository")

    replay = reconstruct_state(run_id)
    assert replay["state"] == RuntimeState.completed.value
    assert replay["selected_action_kind"] == "list_dir"
    assert replay["latest_receipt"]["status"] == "success"
    assert replay["discrepancies"] == []
    assert replay["selected_action"]["binding"]["action_fingerprint"] == (
        replay["latest_receipt"]["binding"]["action_fingerprint"]
    )
    assert any(
        entry["name"] == "README.md"
        for entry in replay["latest_receipt"]["outputs"]["entries"]
    )


def test_run_searches_workspace(monkeypatch, tmp_path):
    monkeypatch.setenv("HCA_STORAGE_ROOT", str(tmp_path / "storage"))

    runtime = Runtime()
    run_id = runtime.run(
        "search for `RuntimeState` in `hca/src/hca/common/enums.py`"
    )

    replay = reconstruct_state(run_id)
    assert replay["state"] == RuntimeState.completed.value
    assert replay["active_workflow"]["workflow_class"] == "investigation"
    search_step = next(
        step
        for step in replay["workflow_step_history"]
        if step["step_key"] == "search"
    )
    assert search_step["outputs"]["returned"] >= 1
    assert search_step["outputs"]["matches"][0]["path"] == (
        "hca/src/hca/common/enums.py"
    )


def test_run_investigates_workspace_issue(monkeypatch, tmp_path):
    monkeypatch.setenv("HCA_STORAGE_ROOT", str(tmp_path / "storage"))

    runtime = Runtime()
    run_id = runtime.run(
        "investigate contract mismatch for `RuntimeState` in "
        "`hca/src/hca/common/enums.py`"
    )

    replay = reconstruct_state(run_id)
    assert replay["state"] == RuntimeState.completed.value
    assert replay["active_workflow"]["workflow_class"] == (
        "contract_api_drift"
    )
    assert replay["active_workflow"]["strategy"] == (
        "contract_drift_strategy"
    )
    step_keys = [
        step["step_key"] for step in replay["workflow_step_history"]
    ]
    assert step_keys == [
        "target_glob",
        "target_search",
        "target_read_context",
        "contract_surface_search",
        "contract_surface_read_context",
        "contract_surface_summary",
        "run_report",
    ]
    assert replay["artifacts_count"] >= 2
    summary_step = next(
        step
        for step in replay["workflow_step_history"]
        if step["step_key"] == "contract_surface_summary"
    )
    assert summary_step["artifacts"]
    assert any(
        "contract_drift_summary" in artifact
        for artifact in summary_step["artifacts"]
    )


def test_run_investigates_generic_workspace_phrase(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("HCA_STORAGE_ROOT", str(tmp_path / "storage"))

    runtime = Runtime()
    run_id = runtime.run(
        "investigate RuntimeState in hca/src/hca/common/enums.py"
    )

    replay = reconstruct_state(run_id)
    assert replay["state"] == RuntimeState.completed.value
    assert replay["active_workflow"]["workflow_class"] == (
        "investigation"
    )
    search_step = next(
        step
        for step in replay["workflow_step_history"]
        if step["step_key"] == "search"
    )
    assert search_step["outputs"]["matches"][0]["path"] == (
        "hca/src/hca/common/enums.py"
    )


def test_workflow_budget_exhaustion_fails_closed(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("HCA_STORAGE_ROOT", str(tmp_path / "storage"))

    workflow_plan = WorkflowPlan(
        workflow_class=WorkflowClass.investigation,
        strategy="budget_test_strategy",
        steps=[
            WorkflowStep(
                step_key="first_step",
                tool_name="echo",
                arguments_template={"text": "first"},
            ),
            WorkflowStep(
                step_key="second_step",
                tool_name="echo",
                arguments_template={"text": "second"},
            ),
        ],
        parameters={"goal": "exercise workflow budget"},
        rationale="Budget exhaustion should fail closed before step two.",
        confidence=0.91,
        max_steps=1,
        termination_condition="budget_or_completion",
    )
    _stub_workflow_plan(monkeypatch, workflow_plan)

    runtime = Runtime()
    run_id = runtime.run("exercise workflow budget")

    replay = reconstruct_state(run_id)
    assert replay["state"] == RuntimeState.failed.value
    assert replay["workflow_budget"] == {
        "max_steps": 1,
        "consumed_steps": 1,
    }
    assert replay["workflow_outcome"] == {
        "terminal_event": "workflow_terminated",
        "reason": "budget_exhausted",
        "workflow_step_id": None,
        "next_step_id": replay["workflow_checkpoint"]["current_step_id"],
    }
    assert [
        step["step_key"] for step in replay["workflow_step_history"]
    ] == ["first_step"]

    events = list(iter_events(run_id))
    assert any(
        event["event_type"] == "workflow_budget_exhausted"
        for event in events
    )
    run_failed_event = next(
        event for event in events if event["event_type"] == "run_failed"
    )
    assert run_failed_event["payload"]["reason"] == (
        "workflow_budget_exhausted"
    )
    assert run_failed_event["payload"]["workflow_id"] == (
        replay["active_workflow"]["workflow_id"]
    )
    terminated_event = next(
        event
        for event in events
        if event["event_type"] == "workflow_terminated"
        and event["payload"]["reason"] == "budget_exhausted"
    )
    assert terminated_event["payload"]["next_step_id"] == (
        replay["workflow_checkpoint"]["current_step_id"]
    )


def test_workflow_next_step_unbuildable_fails_closed(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("HCA_STORAGE_ROOT", str(tmp_path / "storage"))

    workflow_plan = WorkflowPlan(
        workflow_class=WorkflowClass.investigation,
        strategy="unbuildable_test_strategy",
        steps=[
            WorkflowStep(
                step_key="emit_marker",
                tool_name="echo",
                arguments_template={"text": "marker"},
            ),
            WorkflowStep(
                step_key="missing_reference",
                tool_name="read_text_range",
                arguments_template={
                    "path": "step:emit_marker.outputs.path",
                    "start_line": 1,
                    "end_line": 1,
                },
            ),
        ],
        parameters={"goal": "exercise next step unbuildable"},
        rationale="Missing step outputs should fail closed.",
        confidence=0.9,
        max_steps=2,
        termination_condition="all_steps_completed",
    )
    _stub_workflow_plan(monkeypatch, workflow_plan)

    runtime = Runtime()
    run_id = runtime.run("exercise next step unbuildable")

    replay = reconstruct_state(run_id)
    assert replay["state"] == RuntimeState.failed.value
    assert replay["workflow_outcome"] == {
        "terminal_event": "workflow_terminated",
        "reason": "next_step_unbuildable",
        "workflow_step_id": replay["workflow_checkpoint"]["current_step_id"],
        "next_step_id": None,
    }
    assert [
        step["step_key"] for step in replay["workflow_step_history"]
    ] == ["emit_marker"]

    terminated_event = next(
        event
        for event in iter_events(run_id)
        if event["event_type"] == "workflow_terminated"
    )
    run_failed_event = next(
        event
        for event in iter_events(run_id)
        if event["event_type"] == "run_failed"
    )
    assert terminated_event["payload"]["reason"] == (
        "next_step_unbuildable"
    )
    assert terminated_event["payload"]["workflow_step_id"] == (
        replay["workflow_checkpoint"]["current_step_id"]
    )
    assert run_failed_event["payload"]["reason"] == (
        "workflow_next_step_unbuildable"
    )
    assert run_failed_event["payload"]["workflow_step_id"] == (
        replay["workflow_checkpoint"]["current_step_id"]
    )


def test_run_records_unhandled_exception_as_terminal_failure(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("HCA_STORAGE_ROOT", str(tmp_path / "storage"))

    captured: dict[str, str] = {}

    def _boom(self, context):
        captured["run_id"] = context.run_id
        raise RuntimeError("boom")

    monkeypatch.setattr(Runtime, "_step", _boom)

    runtime = Runtime()
    with pytest.raises(RuntimeError, match="boom"):
        runtime.run("explode")

    replay = reconstruct_state(captured["run_id"])
    assert replay["state"] == RuntimeState.failed.value

    failed_event = next(
        event
        for event in iter_events(captured["run_id"])
        if event["event_type"] == "run_failed"
    )
    assert failed_event["payload"]["reason"] == (
        "unhandled_runtime_exception"
    )
    assert failed_event["payload"]["error_type"] == "RuntimeError"


def test_runtime_executes_mutation_verification_workflow(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("HCA_STORAGE_ROOT", str(tmp_path / "storage"))

    tool_registry = import_module("hca.executor.tool_registry")
    monkeypatch.setattr(tool_registry, "REPO_ROOT", tmp_path)

    notes_dir = tmp_path / "notes"
    notes_dir.mkdir(parents=True, exist_ok=True)
    (notes_dir / "todo.txt").write_text("hello world\n", encoding="utf-8")
    (tmp_path / "test_sample.py").write_text(
        "from pathlib import Path\n\n"
        "def test_todo_updated():\n"
        "    todo = Path('notes/todo.txt').read_text(\n"
        "        encoding='utf-8'\n"
        "    ).strip()\n"
        "    assert todo == 'hello mars'\n",
        encoding="utf-8",
    )

    runtime = Runtime()
    goal = (
        "replace `world` with `mars` in `notes/todo.txt` "
        "and verify with pytest `test_sample.py`"
    )
    run_id = runtime.run(goal)

    paused = reconstruct_state(run_id)
    assert paused["state"] == RuntimeState.awaiting_approval.value
    assert paused["active_workflow"]["workflow_class"] == (
        "mutation_with_verification"
    )
    pending = get_pending_requests(run_id)
    assert len(pending) == 1
    approval_id = pending[0].approval_id

    token = "workflow-approval-token"
    append_grant(run_id, ApprovalGrant(approval_id=approval_id, token=token))
    runtime.resume(run_id, approval_id, token)

    replay = reconstruct_state(run_id)
    assert replay["state"] == RuntimeState.completed.value
    assert Path(tmp_path / "notes" / "todo.txt").read_text(
        encoding="utf-8"
    ) == "hello mars\n"
    assert len(replay["workflow_step_history"]) >= 8

    patch_step = next(
        step
        for step in replay["workflow_step_history"]
        if step["step_key"] == "patch_apply"
    )
    assert patch_step["mutation_result"]["status"] == "applied"
    assert patch_step["touched_paths"] == ["notes/todo.txt"]

    verification_step = next(
        step
        for step in replay["workflow_step_history"]
        if step["step_key"] == "verification"
    )
    assert verification_step["outputs"]["ok"] is True

    artifact_types = {
        artifact["artifact_type"] for artifact in replay["workflow_artifacts"]
    }
    assert {"diff_report", "run_report", "command_result"}.issubset(
        artifact_types
    )


def test_runtime_builds_unquoted_mutation_verification_workflow(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("HCA_STORAGE_ROOT", str(tmp_path / "storage"))

    tool_registry = import_module("hca.executor.tool_registry")
    monkeypatch.setattr(tool_registry, "REPO_ROOT", tmp_path)

    notes_dir = tmp_path / "notes"
    notes_dir.mkdir(parents=True, exist_ok=True)
    (notes_dir / "todo.txt").write_text("hello world\n", encoding="utf-8")
    (tmp_path / "test_sample.py").write_text(
        "def test_placeholder():\n"
        "    assert True\n",
        encoding="utf-8",
    )

    runtime = Runtime()
    run_id = runtime.run(
        "replace world with mars in notes/todo.txt and verify with pytest test_sample.py"
    )

    replay = reconstruct_state(run_id)
    assert replay["state"] == RuntimeState.awaiting_approval.value
    assert replay["active_workflow"]["workflow_class"] == (
        "mutation_with_verification"
    )
    pending = get_pending_requests(run_id)
    assert len(pending) == 1


def test_critic_broadcast_falls_back_without_optional_llm(monkeypatch):
    workspace = Workspace(capacity=3)
    workspace.admit(
        [
            WorkspaceItem(
                item_id="action-1",
                source_module="planner",
                kind="action_suggestion",
                content={"action": "write_artifact", "args": {}},
                confidence=0.9,
            )
        ]
    )

    critic = Critic()
    critic.propose("run-critic-broadcast")

    async def _missing_llm(*args, **kwargs):
        raise ModuleNotFoundError("No module named 'emergentintegrations'")

    monkeypatch.setattr(critic_module, "_llm_evaluate", _missing_llm)
    monkeypatch.setattr(
        critic_module,
        "load_run",
        lambda run_id: RunContext(run_id=run_id, goal="Create an artifact"),
    )

    payloads = broadcast(workspace, [critic])

    assert len(payloads) == 1
    critique_item = payloads[0]["critique_items"][0]["content"]
    assert critique_item["llm_powered"] is False
    assert critique_item["issues"] == [
        "Action write_artifact is missing required fields: content"
    ]
