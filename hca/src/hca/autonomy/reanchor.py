"""Cheap operator-facing re-anchor summaries for autonomy runs."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from hca.autonomy.style_profile import AttentionMode


class ReanchorState(BaseModel):
    primary_goal: str
    current_subgoal: str
    active_reason: str
    queued: List[str] = Field(default_factory=list)
    blocked: List[str] = Field(default_factory=list)
    next_action: str
    attention_mode: AttentionMode = AttentionMode.stable
    continuation_justification: Optional[str] = None


class ReanchorSummary(BaseModel):
    primary_goal: str
    current_subgoal: str
    why_this_thread_is_active: str
    queued: List[str] = Field(default_factory=list)
    blocked: List[str] = Field(default_factory=list)
    next_action: str
    justification: str
    attention_mode: AttentionMode = AttentionMode.stable
    compact_summary: str


def build_reanchor_summary(state: ReanchorState) -> ReanchorSummary:
    queued_text = ", ".join(state.queued[:3]) if state.queued else "none"
    blocked_text = ", ".join(state.blocked[:3]) if state.blocked else "none"
    justification = state.continuation_justification or (
        "continue the active thread because it is still the best bounded path"
    )
    compact = (
        f"Goal: {state.primary_goal} | Active: {state.current_subgoal} | "
        f"Queued: {queued_text} | Blocked: {blocked_text} | Next: {state.next_action}"
    )
    return ReanchorSummary(
        primary_goal=state.primary_goal,
        current_subgoal=state.current_subgoal,
        why_this_thread_is_active=state.active_reason,
        queued=list(state.queued),
        blocked=list(state.blocked),
        next_action=state.next_action,
        justification=justification,
        attention_mode=state.attention_mode,
        compact_summary=compact,
    )
