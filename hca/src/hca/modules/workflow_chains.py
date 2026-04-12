"""Bounded workflow templates and argument resolution helpers."""

from __future__ import annotations

import copy
import re
from pathlib import PurePosixPath
from typing import Any, Dict, List, Optional

from hca.common.enums import WorkflowClass
from hca.common.types import WorkflowPlan, WorkflowStep, WorkflowStepRecord
from hca.modules.workspace_intents import (
    extract_path_hint,
    extract_replace_directive,
    extract_search_query,
)


_QUOTED_SEGMENTS = re.compile(r"[`\"']([^`\"']+)[`\"']")


def _quoted_segments(text: str) -> List[str]:
    return [match.group(1) for match in _QUOTED_SEGMENTS.finditer(text)]


def _extract_test_target(text: str) -> Optional[str]:
    goal_lower = text.lower()
    if not any(
        phrase in goal_lower
        for phrase in (
            "run tests",
            "run test",
            "verify",
            "pytest",
            "cargo test",
            "cargo check",
        )
    ):
        return None

    quoted_paths = [
        segment
        for segment in _quoted_segments(text)
        if segment.endswith(".py") or segment.endswith(".rs")
    ]
    for segment in reversed(quoted_paths):
        name = segment.rsplit("/", 1)[-1]
        if name.startswith("test_") or "/tests/" in f"/{segment}/":
            return segment
    return quoted_paths[-1] if quoted_paths else None


def _default_root(path_hint: Optional[str]) -> str:
    if not path_hint or "/" not in path_hint:
        return "."
    return path_hint.rsplit("/", 1)[0] or "."


def _default_path_glob(path_hint: Optional[str]) -> str:
    if path_hint:
        normalized = PurePosixPath(path_hint)
        return normalized.name or path_hint
    return "**/*.py"


def _contract_surface_root(path_hint: Optional[str]) -> str:
    if not path_hint or "/" not in path_hint:
        return "."
    return path_hint.split("/", 1)[0] or "."


def _contract_surface_glob(path_hint: Optional[str]) -> str:
    if path_hint:
        suffix = PurePosixPath(path_hint).suffix
        if suffix:
            return f"**/*{suffix}"
    return "**/*"


def _verification_command(text: str) -> Optional[Dict[str, Any]]:
    goal_lower = text.lower()
    if "cargo check" in goal_lower:
        return {"argv": ["cargo", "check"], "cwd": ".", "timeout_seconds": 20}

    if "cargo test" in goal_lower:
        return {"argv": ["cargo", "test"], "cwd": ".", "timeout_seconds": 20}

    if any(
        phrase in goal_lower
        for phrase in ("pytest", "run test", "run tests", "verify")
    ):
        target = _extract_test_target(text)
        argv = ["pytest", "-q"]
        if target:
            argv.append(target)
        return {"argv": argv, "cwd": ".", "timeout_seconds": 20}

    return None


def _workflow_parameters(goal: str) -> Dict[str, Any]:
    path_hint = extract_path_hint(goal)
    replace_directive = extract_replace_directive(goal)
    query = extract_search_query(goal)
    verification = _verification_command(goal)

    parameters: Dict[str, Any] = {
        "goal": goal,
        "query": query,
        "root": _default_root(path_hint),
        "path_glob": _default_path_glob(path_hint),
        "target_root": _default_root(path_hint),
        "target_path_glob": _default_path_glob(path_hint),
        "contract_root": _contract_surface_root(path_hint),
        "contract_path_glob": _contract_surface_glob(path_hint),
        "contract_summary_path": "contract_drift_summary.json",
        "context_radius": 2,
    }
    if replace_directive is not None:
        path, old_text, new_text = replace_directive
        parameters["replace"] = {
            "path": path,
            "old_text": old_text,
            "new_text": new_text,
        }
        if not parameters["query"]:
            parameters["query"] = old_text
        parameters["path_glob"] = _default_path_glob(path)
        parameters["root"] = _default_root(path)
        parameters["target_path_glob"] = _default_path_glob(path)
        parameters["target_root"] = _default_root(path)
        parameters["contract_root"] = _contract_surface_root(path)
        parameters["contract_path_glob"] = _contract_surface_glob(path)
    if verification is not None:
        parameters["verification"] = verification
    return parameters


def classify_workflow(goal: str) -> Optional[WorkflowClass]:
    parameters = _workflow_parameters(goal)
    if parameters.get("replace") and parameters.get("verification"):
        return WorkflowClass.mutation_with_verification
    if parameters.get("replace"):
        return WorkflowClass.targeted_mutation
    if any(
        phrase in goal.lower()
        for phrase in (
            "contract mismatch",
            "api mismatch",
            "schema mismatch",
            "interface mismatch",
        )
    ):
        return WorkflowClass.contract_api_drift
    if parameters.get("query"):
        return WorkflowClass.investigation
    if any(
        phrase in goal.lower()
        for phrase in (
            "create report",
            "run report",
            "run summary",
            "summarize this run",
        )
    ):
        return WorkflowClass.report_generation
    return None


def _investigation_steps() -> List[WorkflowStep]:
    return [
        WorkflowStep(
            step_key="glob",
            tool_name="glob_workspace",
            arguments_template={
                "root": "workflow:root",
                "pattern": "workflow:path_glob",
                "max_results": 50,
            },
            description=(
                "List the bounded candidate files before deeper "
                "inspection."
            ),
        ),
        WorkflowStep(
            step_key="search",
            tool_name="search_workspace",
            arguments_template={
                "query": "workflow:query",
                "root": "workflow:root",
                "path_glob": "workflow:path_glob",
                "max_results": 8,
                "max_files": 20,
                "max_total_bytes": 512000,
            },
            description=(
                "Search the bounded workspace for the requested issue "
                "signal."
            ),
        ),
        WorkflowStep(
            step_key="read_context",
            tool_name="read_text_range",
            arguments_template={
                "path": "step:search.outputs.matches.0.path",
                "start_line": {
                    "ref": "step:search.outputs.matches.0.line_number",
                    "offset": -2,
                    "min": 1,
                },
                "end_line": {
                    "ref": "step:search.outputs.matches.0.line_number",
                    "offset": 2,
                    "min": 1,
                },
            },
            description=(
                "Read a tight text window around the first bounded "
                "search hit."
            ),
        ),
        WorkflowStep(
            step_key="summary",
            tool_name="summarize_search_results",
            arguments_template={
                "query": "workflow:query",
                "search_result": "step:search.outputs",
                "excerpt": "step:read_context.outputs",
            },
            description=(
                "Materialize a deterministic investigation summary "
                "artifact."
            ),
        ),
        WorkflowStep(
            step_key="run_report",
            tool_name="create_run_report",
            arguments_template={"projected_final_status": "completed"},
            description="Materialize the final run report artifact.",
        ),
    ]


def _contract_drift_steps() -> List[WorkflowStep]:
    return [
        WorkflowStep(
            step_key="target_glob",
            tool_name="glob_workspace",
            arguments_template={
                "root": "workflow:target_root",
                "pattern": "workflow:target_path_glob",
                "max_results": 20,
            },
            description=(
                "List the bounded target files implicated in the reported "
                "contract drift."
            ),
        ),
        WorkflowStep(
            step_key="target_search",
            tool_name="search_workspace",
            arguments_template={
                "query": "workflow:query",
                "root": "workflow:target_root",
                "path_glob": "workflow:target_path_glob",
                "max_results": 8,
                "max_files": 12,
                "max_total_bytes": 256000,
            },
            description=(
                "Search the bounded target surface for the contract signal "
                "that appears to have drifted."
            ),
        ),
        WorkflowStep(
            step_key="target_read_context",
            tool_name="read_text_range",
            arguments_template={
                "path": "step:target_search.outputs.matches.0.path",
                "start_line": {
                    "ref": "step:target_search.outputs.matches.0.line_number",
                    "offset": -2,
                    "min": 1,
                },
                "end_line": {
                    "ref": "step:target_search.outputs.matches.0.line_number",
                    "offset": 2,
                    "min": 1,
                },
            },
            description=(
                "Read the bounded target context around the first drift "
                "signal."
            ),
        ),
        WorkflowStep(
            step_key="contract_surface_search",
            tool_name="search_workspace",
            arguments_template={
                "query": "workflow:query",
                "root": "workflow:contract_root",
                "path_glob": "workflow:contract_path_glob",
                "max_results": 12,
                "max_files": 24,
                "max_total_bytes": 512000,
            },
            description=(
                "Search the broader bounded surface for matching contract or "
                "interface evidence."
            ),
        ),
        WorkflowStep(
            step_key="contract_surface_read_context",
            tool_name="read_text_range",
            arguments_template={
                "path": "step:contract_surface_search.outputs.matches.0.path",
                "start_line": {
                    "ref": "step:contract_surface_search.outputs.matches.0"
                    ".line_number",
                    "offset": -2,
                    "min": 1,
                },
                "end_line": {
                    "ref": "step:contract_surface_search.outputs.matches.0"
                    ".line_number",
                    "offset": 2,
                    "min": 1,
                },
            },
            description=(
                "Read the bounded comparison context from the wider contract "
                "surface."
            ),
        ),
        WorkflowStep(
            step_key="contract_surface_summary",
            tool_name="summarize_search_results",
            arguments_template={
                "query": "workflow:query",
                "search_result": "step:contract_surface_search.outputs",
                "excerpt": "step:contract_surface_read_context.outputs",
                "path": "workflow:contract_summary_path",
            },
            description=(
                "Materialize a deterministic contract-drift summary artifact "
                "from the bounded comparison surface."
            ),
        ),
        WorkflowStep(
            step_key="run_report",
            tool_name="create_run_report",
            arguments_template={"projected_final_status": "completed"},
            description="Materialize the final run report artifact.",
        ),
    ]


def _mutation_steps(include_verification: bool) -> List[WorkflowStep]:
    steps = _investigation_steps()[:-1]
    steps.extend(
        [
            WorkflowStep(
                step_key="patch_preview",
                tool_name="patch_text_file",
                arguments_template={
                    "path": "workflow:replace.path",
                    "old_text": "workflow:replace.old_text",
                    "new_text": "workflow:replace.new_text",
                    "apply": False,
                },
                description=(
                    "Preview the proposed bounded patch and capture its "
                    "hash guard."
                ),
            ),
            WorkflowStep(
                step_key="patch_apply",
                tool_name="patch_text_file",
                arguments_template={
                    "path": "workflow:replace.path",
                    "old_text": "workflow:replace.old_text",
                    "new_text": "workflow:replace.new_text",
                    "apply": True,
                    "expected_hash": "step:patch_preview.outputs.before_hash",
                },
                description="Apply the approved bounded patch.",
            ),
            WorkflowStep(
                step_key="diff_report",
                tool_name="create_diff_report",
                arguments_template={
                    "target_path": "workflow:replace.path",
                    "before_hash": "step:patch_apply.outputs.before_hash",
                    "after_hash": "step:patch_apply.outputs.after_hash",
                    "changed_lines": "step:patch_apply.outputs.changed_lines",
                    "diff_artifact_path": (
                        "step:patch_apply.outputs.diff_artifact_path"
                    ),
                    "approval_id": "step:patch_apply.approval_id",
                },
                description="Materialize a structured diff report artifact.",
            ),
        ]
    )
    if include_verification:
        steps.append(
            WorkflowStep(
                step_key="verification",
                tool_name="run_command",
                arguments_template={
                    "argv": "workflow:verification.argv",
                    "cwd": "workflow:verification.cwd",
                    "timeout_seconds": "workflow:verification.timeout_seconds",
                },
                description=(
                    "Run the bounded verification command for the "
                    "targeted change."
                ),
            )
        )
    steps.append(
        WorkflowStep(
            step_key="run_report",
            tool_name="create_run_report",
            arguments_template={"projected_final_status": "completed"},
            description="Materialize the final run report artifact.",
        )
    )
    return steps


def build_workflow_plan(goal: str) -> Optional[WorkflowPlan]:
    workflow_class = classify_workflow(goal)
    if workflow_class is None:
        return None

    parameters = _workflow_parameters(goal)
    if workflow_class == WorkflowClass.report_generation:
        steps = [
            WorkflowStep(
                step_key="run_report",
                tool_name="create_run_report",
                arguments_template={"projected_final_status": "completed"},
                description="Materialize the final run report artifact.",
            )
        ]
        strategy = "run_reporting_strategy"
    elif workflow_class in {
        WorkflowClass.investigation,
    }:
        if not parameters.get("query"):
            return None
        steps = _investigation_steps()
        strategy = "investigation_strategy"
    elif workflow_class == WorkflowClass.contract_api_drift:
        if not parameters.get("query"):
            return None
        steps = _contract_drift_steps()
        strategy = "contract_drift_strategy"
    elif workflow_class == WorkflowClass.targeted_mutation:
        if not parameters.get("replace"):
            return None
        steps = _mutation_steps(include_verification=False)
        strategy = "workspace_mutation_strategy"
    else:
        if not parameters.get("replace") or not parameters.get("verification"):
            return None
        steps = _mutation_steps(include_verification=True)
        strategy = "mutation_verification_strategy"

    return WorkflowPlan(
        workflow_class=workflow_class,
        strategy=strategy,
        steps=steps,
        parameters=parameters,
        rationale=(
            "Bounded workflow selected from explicit task classification."
        ),
        confidence=0.72,
        max_steps=len(steps),
        termination_condition="all_steps_completed",
    )


def _resolve_reference(
    reference: str,
    workflow: WorkflowPlan,
    step_history: List[WorkflowStepRecord],
) -> Any:
    if reference.startswith("workflow:"):
        value: Any = workflow.parameters
        parts = reference.split(":", 1)[1].split(".")
    elif reference.startswith("step:"):
        _, remainder = reference.split(":", 1)
        step_key, _, path = remainder.partition(".")
        value = next(
            (
                record.model_dump(mode="json")
                for record in reversed(step_history)
                if record.step_key == step_key or record.step_id == step_key
            ),
            None,
        )
        parts = path.split(".") if path else []
    else:
        return reference

    for part in parts:
        if part == "":
            continue
        try:
            if isinstance(value, list):
                value = value[int(part)]
            elif isinstance(value, dict):
                value = value[part]
            else:
                raise KeyError(reference)
        except (IndexError, KeyError, TypeError, ValueError) as exc:
            raise KeyError(reference) from exc
    return copy.deepcopy(value)


def resolve_step_arguments(
    workflow: WorkflowPlan,
    step: WorkflowStep,
    *,
    step_history: List[WorkflowStepRecord],
) -> Dict[str, Any]:
    def _resolve(value: Any) -> Any:
        if isinstance(value, str) and (
            value.startswith("workflow:") or value.startswith("step:")
        ):
            return _resolve_reference(value, workflow, step_history)
        if isinstance(value, dict):
            if "ref" in value:
                resolved = _resolve_reference(
                    str(value["ref"]), workflow, step_history
                )
                if isinstance(resolved, (int, float)):
                    resolved += int(value.get("offset", 0))
                    if "min" in value:
                        resolved = max(int(value["min"]), int(resolved))
                    if "max" in value:
                        resolved = min(int(value["max"]), int(resolved))
                return resolved
            return {key: _resolve(item) for key, item in value.items()}
        if isinstance(value, list):
            return [_resolve(item) for item in value]
        return value

    return {
        key: _resolve(value)
        for key, value in step.arguments_template.items()
    }
