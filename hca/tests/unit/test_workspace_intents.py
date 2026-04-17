from hca.common.enums import WorkflowClass
from hca.modules.workflow_chains import build_workflow_plan
from hca.modules.workspace_intents import (
    extract_replace_directive,
    extract_search_query,
    infer_workspace_action_from_text,
)


def test_extract_search_query_strips_workspace_filler():
    assert extract_search_query("search the repo for RuntimeState") == (
        "RuntimeState"
    )
    assert extract_search_query(
        "look for RuntimeState in hca/src/hca/common/enums.py"
    ) == "RuntimeState"


def test_extract_replace_directive_supports_unquoted_path_like_tokens():
    assert extract_replace_directive(
        "replace world with mars in notes/todo.txt"
    ) == ("notes/todo.txt", "world", "mars")
    assert extract_replace_directive(
        "replace /runs with /api/hca/runs in frontend/src/App.js"
    ) == (
        "frontend/src/App.js",
        "/runs",
        "/api/hca/runs",
    )


def test_infer_workspace_action_from_generic_investigate_phrase():
    action, arguments = infer_workspace_action_from_text(
        "investigate RuntimeState in hca/src/hca/common/enums.py"
    )

    assert action == "investigate_workspace_issue"
    assert arguments == {
        "query": "RuntimeState",
        "path_glob": "hca/src/hca/common/enums.py",
    }


def test_build_workflow_plan_classifies_unquoted_mutation_verification():
    workflow = build_workflow_plan(
        "replace world with mars in notes/todo.txt and verify with pytest test_sample.py"
    )

    assert workflow is not None
    assert workflow.workflow_class == WorkflowClass.mutation_with_verification
    assert workflow.parameters["replace"] == {
        "path": "notes/todo.txt",
        "old_text": "world",
        "new_text": "mars",
    }
    assert workflow.parameters["verification"] == {
        "argv": ["pytest", "-q", "test_sample.py"],
        "cwd": ".",
        "timeout_seconds": 20,
    }