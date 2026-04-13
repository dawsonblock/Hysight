import hca.modules.perception_text as perception_module
from hca.common.types import RunContext


def _perceived_intent_content(proposal):
    return next(
        item.content
        for item in proposal.candidate_items
        if item.kind == "perceived_intent"
    )


def test_perception_surfaces_llm_failure(monkeypatch):
    perception = perception_module.TextPerception()

    async def _llm_failure(*_args, **_kwargs):
        raise RuntimeError("llm unavailable")

    monkeypatch.setattr(
        perception_module,
        "load_run",
        lambda run_id: RunContext(run_id=run_id, goal="find the API key"),
    )
    monkeypatch.setattr(perception_module, "_llm_perceive", _llm_failure)

    proposal = perception.propose("run-perception-fallback")
    perceived_intent = _perceived_intent_content(proposal)

    assert perceived_intent["intent_class"] == "retrieve_memory"
    assert perceived_intent["intent"] == "retrieve"
    assert perceived_intent["perception_mode"] == "rule_based_fallback"
    assert perceived_intent["fallback_reason"] == "llm_error:RuntimeError"
    assert perceived_intent["llm_attempted"] is True


def test_perception_marks_missing_goal_without_attempting_llm(monkeypatch):
    perception = perception_module.TextPerception()

    monkeypatch.setattr(perception_module, "load_run", lambda run_id: None)
    monkeypatch.setattr(
        perception_module,
        "_llm_perceive",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("llm perception should not be attempted")
        ),
    )

    proposal = perception.propose("run-perception-no-goal")
    perceived_intent = _perceived_intent_content(proposal)

    assert perceived_intent["intent_class"] == "general"
    assert perceived_intent["intent"] == "general"
    assert perceived_intent["perception_mode"] == "rule_based_only"
    assert perceived_intent["fallback_reason"] == "missing_goal"
    assert perceived_intent["llm_attempted"] is False
