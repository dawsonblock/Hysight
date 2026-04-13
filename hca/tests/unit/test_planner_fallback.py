from importlib import import_module

import hca.modules.planner as planner_module
from hca.common.types import RunContext


def _task_plan_content(proposal):
    return next(
        item.content
        for item in proposal.candidate_items
        if item.kind == "task_plan"
    )


def test_planner_surfaces_memory_retrieval_failure(monkeypatch):
    planner = planner_module.Planner()
    singleton_module = import_module("memory_service.singleton")

    class _ExplodingController:
        def retrieve(self, *_args, **_kwargs):
            raise RuntimeError("memory backend unavailable")

    async def _llm_failure(*_args, **_kwargs):
        raise RuntimeError("llm unavailable")

    monkeypatch.setattr(
        planner_module,
        "load_run",
        lambda run_id: RunContext(run_id=run_id, goal="general hello"),
    )
    monkeypatch.setattr(
        planner_module,
        "build_workflow_plan",
        lambda goal: None,
    )
    monkeypatch.setattr(planner_module, "_llm_plan", _llm_failure)
    monkeypatch.setattr(
        singleton_module,
        "get_controller",
        lambda: _ExplodingController(),
    )

    proposal = planner.propose("run-planner-memory-fallback")
    task_plan = _task_plan_content(proposal)

    assert task_plan["planning_mode"] == "rule_based_fallback"
    assert task_plan["fallback_reason"] == "llm_error:RuntimeError"
    assert task_plan["memory_context_used"] is False
    assert task_plan["memory_retrieval_status"] == "failed"
    assert task_plan["memory_retrieval_error"] == "RuntimeError"
    assert task_plan["memory_hits"] == []


def test_planner_marks_memory_lookup_not_attempted_without_goal(monkeypatch):
    planner = planner_module.Planner()
    singleton_module = import_module("memory_service.singleton")

    monkeypatch.setattr(planner_module, "load_run", lambda run_id: None)
    monkeypatch.setattr(
        singleton_module,
        "get_controller",
        lambda: (_ for _ in ()).throw(
            AssertionError("memory retrieval should not be attempted")
        ),
    )

    proposal = planner.propose("run-planner-no-goal")
    task_plan = _task_plan_content(proposal)

    assert task_plan["planning_mode"] == "rule_based_fallback"
    assert task_plan["fallback_reason"] == "missing_goal"
    assert task_plan["memory_retrieval_status"] == "not_attempted"
    assert task_plan["memory_retrieval_error"] is None
