"""Style profile unit tests for the bounded autonomy cognition layer."""

from pydantic import ValidationError

from hca.autonomy.style_profile import (
    AttentionMode,
    get_style_profile,
    list_style_profiles,
)


def test_builtin_profiles_load_correctly():
    profiles = {profile.profile_id for profile in list_style_profiles()}
    assert "conservative_operator" in profiles
    assert "dawson_like_operator" in profiles

    conservative = get_style_profile("conservative_operator")
    dawson = get_style_profile("dawson_like_operator")

    assert conservative.enabled is True
    assert dawson.enabled is True
    assert conservative.default_attention_mode == AttentionMode.stable
    assert dawson.default_attention_mode in {
        AttentionMode.exploratory,
        AttentionMode.stable,
    }


def test_profile_limits_are_enforced():
    conservative = get_style_profile("conservative_operator")
    assert conservative.max_parallel_subgoals >= 1
    assert conservative.reanchor_interval_steps >= 1
    assert conservative.hyperfocus_max_steps >= 1

    try:
        conservative.model_copy(
            update={"max_parallel_subgoals": 0},
            deep=True,
        )
    except ValidationError:
        return
    raise AssertionError("expected max_parallel_subgoals validation to fail")


def test_dawson_like_profile_biases_novelty_pattern_and_compression():
    conservative = get_style_profile("conservative_operator")
    dawson = get_style_profile("dawson_like_operator")

    assert (
        dawson.trait_weights.novelty_seeking
        > conservative.trait_weights.novelty_seeking
    )
    assert (
        dawson.trait_weights.pattern_hunting
        > conservative.trait_weights.pattern_hunting
    )
    assert (
        dawson.trait_weights.compression_preference
        > conservative.trait_weights.compression_preference
    )
    assert (
        dawson.trait_weights.external_memory_dependence
        >= conservative.trait_weights.external_memory_dependence
    )
