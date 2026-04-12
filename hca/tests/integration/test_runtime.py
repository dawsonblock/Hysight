# mypy: ignore-errors
# pyright: reportMissingImports=false, reportMissingTypeStubs=false

from importlib import import_module

critic_module = import_module("hca.modules.critic")
common_types = import_module("hca.common.types")
common_enums = import_module("hca.common.enums")
replay_module = import_module("hca.runtime.replay")
runtime_module = import_module("hca.runtime.runtime")
broadcast_module = import_module("hca.workspace.broadcast")
workspace_module = import_module("hca.workspace.workspace")

RunContext = common_types.RunContext
RuntimeState = common_enums.RuntimeState
WorkspaceItem = common_types.WorkspaceItem
Critic = critic_module.Critic
Runtime = runtime_module.Runtime
reconstruct_state = replay_module.reconstruct_state
broadcast = broadcast_module.broadcast
Workspace = workspace_module.Workspace


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
