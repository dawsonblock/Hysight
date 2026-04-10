import hca.modules.critic as critic_module
from hca.common.types import RunContext, WorkspaceItem
from hca.modules.critic import Critic
from hca.runtime.runtime import Runtime
from hca.workspace.broadcast import broadcast
from hca.workspace.workspace import Workspace


def test_run_completes():
    runtime = Runtime()
    run_id = runtime.run("echo greeting")
    assert isinstance(run_id, str)


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