# mypy: ignore-errors
# pyright: reportMissingImports=false, reportMissingTypeStubs=false

from importlib import import_module
from pathlib import Path

critic_module = import_module("hca.modules.critic")
common_types = import_module("hca.common.types")
common_enums = import_module("hca.common.enums")
replay_module = import_module("hca.runtime.replay")
runtime_module = import_module("hca.runtime.runtime")
broadcast_module = import_module("hca.workspace.broadcast")
workspace_module = import_module("hca.workspace.workspace")
approvals_module = import_module("hca.storage.approvals")

RunContext = common_types.RunContext
RuntimeState = common_enums.RuntimeState
WorkspaceItem = common_types.WorkspaceItem
ApprovalGrant = common_types.ApprovalGrant
Critic = critic_module.Critic
Runtime = runtime_module.Runtime
reconstruct_state = replay_module.reconstruct_state
broadcast = broadcast_module.broadcast
Workspace = workspace_module.Workspace
append_grant = approvals_module.append_grant
get_pending_requests = approvals_module.get_pending_requests


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
    assert replay["artifacts_count"] >= 2
    summary_step = next(
        step
        for step in replay["workflow_step_history"]
        if step["step_key"] == "summary"
    )
    assert summary_step["artifacts"]


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
