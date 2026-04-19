"""Bounded operator-style profiles for the autonomy supervisor.

These profiles intentionally describe controllable work styles rather than
medical or diagnostic behavior. They bias prioritization, memory emphasis,
and re-anchoring inside the existing bounded policy surface.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class AttentionMode(str, Enum):
    stable = "stable"
    exploratory = "exploratory"
    hyperfocus = "hyperfocus"
    reanchor = "reanchor"


class StyleTraitWeights(BaseModel):
    fast_context_switching: float = Field(default=0.35, ge=0.0, le=1.0)
    novelty_seeking: float = Field(default=0.25, ge=0.0, le=1.0)
    hyperfocus_bursting: float = Field(default=0.35, ge=0.0, le=1.0)
    interrupt_sensitivity: float = Field(default=0.35, ge=0.0, le=1.0)
    non_linear_planning: float = Field(default=0.30, ge=0.0, le=1.0)
    external_memory_dependence: float = Field(default=0.55, ge=0.0, le=1.0)
    time_blindness_risk: float = Field(default=0.20, ge=0.0, le=1.0)
    boredom_decay: float = Field(default=0.25, ge=0.0, le=1.0)
    pattern_hunting: float = Field(default=0.45, ge=0.0, le=1.0)
    compression_preference: float = Field(default=0.45, ge=0.0, le=1.0)


class StyleDecisionHints(BaseModel):
    preferred_attention_mode: AttentionMode = AttentionMode.stable
    prefer_active_threads: bool = True
    prefer_recent_anomalies: bool = True
    prefer_compressed_memory: bool = True
    restate_goal_on_switch: bool = True
    return_to_primary_after_interrupt: bool = True
    operator_priority_bias: float = Field(default=0.2, ge=0.0, le=1.0)
    memory_retrieval_bias: float = Field(default=0.2, ge=0.0, le=1.0)


class OperatorStyleProfile(BaseModel):
    profile_id: str
    name: str
    description: str
    trait_weights: StyleTraitWeights = Field(default_factory=StyleTraitWeights)
    max_parallel_subgoals: int = Field(default=1, ge=1, le=4)
    reanchor_interval_steps: int = Field(default=4, ge=1, le=100)
    mandatory_goal_restatement: bool = True
    novelty_exploration_budget: int = Field(default=1, ge=0, le=20)
    hyperfocus_max_steps: int = Field(default=3, ge=1, le=50)
    interrupt_queue_enabled: bool = True
    deadline_visibility_required: bool = True
    forced_checkpoint_before_switch: bool = True
    forced_checkpoint_after_write: bool = True
    enabled: bool = True
    default_attention_mode: AttentionMode = AttentionMode.stable
    decision_hints: StyleDecisionHints = Field(default_factory=StyleDecisionHints)

    def model_copy(self, *, update: Dict[str, object] | None = None, deep: bool = False):
        copied = super().model_copy(update=update, deep=deep)
        return type(self).model_validate(copied.model_dump(mode="python"))

    @property
    def novelty_budget_remaining(self) -> int:
        return max(0, self.novelty_exploration_budget)


_BUILTIN_PROFILES: Dict[str, OperatorStyleProfile] = {
    "conservative_operator": OperatorStyleProfile(
        profile_id="conservative_operator",
        name="Conservative Operator",
        description=(
            "Low-drift, checkpoint-heavy bounded mode that favors staying on "
            "the primary thread and re-anchoring early."
        ),
        trait_weights=StyleTraitWeights(
            fast_context_switching=0.20,
            novelty_seeking=0.15,
            hyperfocus_bursting=0.30,
            interrupt_sensitivity=0.20,
            non_linear_planning=0.25,
            external_memory_dependence=0.50,
            time_blindness_risk=0.10,
            boredom_decay=0.10,
            pattern_hunting=0.35,
            compression_preference=0.40,
        ),
        max_parallel_subgoals=1,
        reanchor_interval_steps=3,
        mandatory_goal_restatement=True,
        novelty_exploration_budget=1,
        hyperfocus_max_steps=2,
        interrupt_queue_enabled=True,
        deadline_visibility_required=True,
        forced_checkpoint_before_switch=True,
        forced_checkpoint_after_write=True,
        enabled=True,
        default_attention_mode=AttentionMode.stable,
        decision_hints=StyleDecisionHints(
            preferred_attention_mode=AttentionMode.stable,
            prefer_active_threads=True,
            prefer_recent_anomalies=True,
            prefer_compressed_memory=True,
            restate_goal_on_switch=True,
            return_to_primary_after_interrupt=True,
            operator_priority_bias=0.15,
            memory_retrieval_bias=0.20,
        ),
    ),
    "dawson_like_operator": OperatorStyleProfile(
        profile_id="dawson_like_operator",
        name="Dawson-like Operator",
        description=(
            "Fast-pivoting but bounded operator mode that favors pattern "
            "detection, compressed reasoning, short hyperfocus bursts, and "
            "strong external re-anchoring."
        ),
        trait_weights=StyleTraitWeights(
            fast_context_switching=0.62,
            novelty_seeking=0.72,
            hyperfocus_bursting=0.78,
            interrupt_sensitivity=0.64,
            non_linear_planning=0.72,
            external_memory_dependence=0.82,
            time_blindness_risk=0.42,
            boredom_decay=0.58,
            pattern_hunting=0.88,
            compression_preference=0.84,
        ),
        max_parallel_subgoals=2,
        reanchor_interval_steps=4,
        mandatory_goal_restatement=True,
        novelty_exploration_budget=2,
        hyperfocus_max_steps=3,
        interrupt_queue_enabled=True,
        deadline_visibility_required=True,
        forced_checkpoint_before_switch=True,
        forced_checkpoint_after_write=True,
        enabled=True,
        default_attention_mode=AttentionMode.exploratory,
        decision_hints=StyleDecisionHints(
            preferred_attention_mode=AttentionMode.exploratory,
            prefer_active_threads=True,
            prefer_recent_anomalies=True,
            prefer_compressed_memory=True,
            restate_goal_on_switch=True,
            return_to_primary_after_interrupt=True,
            operator_priority_bias=0.28,
            memory_retrieval_bias=0.32,
        ),
    ),
}


def list_style_profiles() -> List[OperatorStyleProfile]:
    return [profile.model_copy(deep=True) for profile in _BUILTIN_PROFILES.values()]


def get_style_profile(profile_id: Optional[str]) -> OperatorStyleProfile:
    key = (profile_id or "conservative_operator").strip() or "conservative_operator"
    try:
        return _BUILTIN_PROFILES[key].model_copy(deep=True)
    except KeyError as exc:
        raise ValueError(f"unknown style profile: {key}") from exc
