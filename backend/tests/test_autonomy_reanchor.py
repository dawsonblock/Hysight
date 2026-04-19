"""Re-anchor summary tests for the bounded operator-style cognition layer."""

from hca.autonomy.checkpoint import AutonomyCheckpoint
from hca.autonomy.reanchor import ReanchorState, build_reanchor_summary
from hca.autonomy.style_profile import AttentionMode


def test_reanchor_summary_contains_primary_current_blocked_and_next_action():
    state = ReanchorState(
        primary_goal="ship the release truthfully",
        current_subgoal="verify autonomy receipts",
        active_reason="local proof is still in progress",
        queued=["frontend cleanup"],
        blocked=["waiting for approval"],
        next_action="rerun autonomy proof",
        attention_mode=AttentionMode.reanchor,
    )

    summary = build_reanchor_summary(state)
    assert summary.primary_goal == "ship the release truthfully"
    assert summary.current_subgoal == "verify autonomy receipts"
    assert summary.blocked == ["waiting for approval"]
    assert summary.next_action == "rerun autonomy proof"
    assert "ship the release truthfully" in summary.compact_summary


def test_reanchor_summary_updates_after_branch_switch():
    first = build_reanchor_summary(
        ReanchorState(
            primary_goal="finish operator patch",
            current_subgoal="initial branch",
            active_reason="new evidence arrived",
            queued=["interrupt A"],
            blocked=[],
            next_action="checkpoint and switch",
            attention_mode=AttentionMode.exploratory,
        )
    )
    second = build_reanchor_summary(
        ReanchorState(
            primary_goal="finish operator patch",
            current_subgoal="interrupt A",
            active_reason="urgent queued interrupt is now active",
            queued=["initial branch"],
            blocked=[],
            next_action="resolve interrupt A",
            attention_mode=AttentionMode.hyperfocus,
        )
    )

    assert first.current_subgoal != second.current_subgoal
    assert second.queued == ["initial branch"]


def test_restart_preserves_or_rebuilds_reanchor_state_correctly():
    summary = build_reanchor_summary(
        ReanchorState(
            primary_goal="keep the run bounded",
            current_subgoal="resume checkpoint",
            active_reason="restart recovery",
            queued=["follow-up"],
            blocked=[],
            next_action="restate goal and continue",
            attention_mode=AttentionMode.reanchor,
        )
    )
    checkpoint = AutonomyCheckpoint(
        agent_id="agent-1",
        trigger_id="trigger-1",
        status="observing",
        last_reanchor_summary=summary.model_dump(mode="json"),
        current_attention_mode=AttentionMode.reanchor.value,
    )

    restored = AutonomyCheckpoint.model_validate(
        checkpoint.model_dump(mode="json")
    )
    assert restored.last_reanchor_summary is not None
    assert restored.last_reanchor_summary["primary_goal"] == "keep the run bounded"
    assert restored.current_attention_mode == AttentionMode.reanchor.value
