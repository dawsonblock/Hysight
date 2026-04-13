from typing import Dict, Optional

import pytest

import hca.modules.critic as critic_module
from hca.common.types import RunContext, WorkspaceItem
from hca.modules.critic import Critic, _rule_based_critique


def _action_item(
    item_id: str,
    action: str,
    args: Optional[Dict[str, str]] = None,
    confidence: float = 0.9,
) -> WorkspaceItem:
    return WorkspaceItem(
        item_id=item_id,
        source_module="planner",
        kind="action_suggestion",
        content={"action": action, "args": args or {}},
        confidence=confidence,
    )


def test_rule_based_critique_formats_action_kind_conflicts():
    critique = _rule_based_critique(
        [
            _action_item("action-1", "echo", {"text": "hello"}),
            _action_item("action-2", "store_note", {"note": "hello"}),
        ]
    )

    assert critique["verdict"] == "revise"
    assert critique["issues"] == [
        "Conflicting actions proposed: echo vs store_note"
    ]
    assert critique["confidence_delta"] == pytest.approx(-0.05)
    assert critique["llm_powered"] is False


def test_rule_based_critique_formats_action_arg_conflicts():
    critique = _rule_based_critique(
        [
            _action_item("action-1", "store_note", {"note": "hello"}),
            _action_item("action-2", "store_note", {"note": "goodbye"}),
        ]
    )

    assert critique["issues"] == [
        "Action store_note has conflicting arguments"
    ]
    assert critique["confidence_delta"] == pytest.approx(-0.05)


def test_rule_based_critique_formats_memory_contradictions_and_missing_fields(
):
    critique = _rule_based_critique(
        [
            _action_item("action-1", "write_artifact", {}),
            WorkspaceItem(
                item_id="memory-1",
                source_module="memory",
                kind="memory_retrieval",
                content=[],
                contradiction_status=True,
            ),
        ]
    )

    assert critique["verdict"] == "revise"
    assert critique["issues"] == [
        "Workspace contains contradiction-linked items",
        "Action write_artifact is missing required fields: content",
    ]
    assert critique["confidence_delta"] == pytest.approx(-0.07)


def test_on_broadcast_falls_back_when_llm_dependency_is_unavailable(
    monkeypatch,
):
    critic = Critic()
    critic.propose("run-critic-fallback")

    async def _missing_llm(*args, **kwargs):
        raise ModuleNotFoundError("No module named 'emergentintegrations'")

    monkeypatch.setattr(critic_module, "_llm_evaluate", _missing_llm)
    monkeypatch.setattr(
        critic_module,
        "load_run",
        lambda run_id: RunContext(run_id=run_id, goal="Create an artifact"),
    )

    result = critic.on_broadcast(
        [_action_item("action-1", "write_artifact", {})]
    )

    assert result["revised_proposals"] == []
    assert len(result["confidence_adjustments"]) == 1
    assert result["confidence_adjustments"][0][
        "new_confidence"
    ] == pytest.approx(0.88)

    critique_item = result["critique_items"][0]["content"]
    assert critique_item["verdict"] == "revise"
    assert critique_item["llm_powered"] is False
    assert (
        critique_item["fallback_reason"]
        == "llm_error:ModuleNotFoundError"
    )
    assert critique_item["issues"] == [
        "Action write_artifact is missing required fields: content"
    ]
