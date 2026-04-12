"""Tool reasoning module for proposing action candidates."""

from __future__ import annotations

from typing import List, Union

from hca.common.types import ModuleProposal, WorkspaceItem
from hca.modules.workflow_chains import (
    build_workflow_plan,
    resolve_step_arguments,
)
from hca.modules.workspace_intents import infer_workspace_action_from_text
from hca.storage import load_run


class ToolReasoner:
    name = "tool_reasoner"

    def update(self, items: List[WorkspaceItem]) -> None:
        """Update internal state based on workspace content."""
        pass

    def on_broadcast(self, items: List[WorkspaceItem]):
        intent_class = None
        perceived_arguments = {}
        strategy = None
        critiques: List[str] = []
        for item in items:
            if item.kind == "perceived_intent":
                intent_class = item.content.get("intent_class")
                perceived_arguments = item.content.get("arguments", {})
            elif item.kind == "task_plan":
                strategy = item.content.get("strategy")
            elif item.kind == "action_critique":
                critiques.extend(item.content.get("critiques", []))

        revised_proposals = []
        desired_action = None
        desired_args = {}
        desired_workflow = None
        if intent_class == "store_note":
            desired_action = "store_note"
            desired_args = {
                "note": perceived_arguments.get(
                    "note", perceived_arguments.get("text", "")
                )
            }
        elif intent_class == "retrieve_memory":
            inferred_action, inferred_args = infer_workspace_action_from_text(
                str(perceived_arguments.get("query", ""))
            )
            if inferred_action is not None:
                desired_action = inferred_action
                desired_args = inferred_args
            else:
                desired_action = "echo"
                desired_args = {
                    "text": (
                        f"Searching for: {perceived_arguments.get('query')}"
                    )
                }
        elif intent_class == "write_artifact":
            desired_action = "write_artifact"
            desired_args = dict(perceived_arguments)
        elif intent_class == "general":
            desired_action, desired_args = infer_workspace_action_from_text(
                str(perceived_arguments.get("text", ""))
            )
            desired_workflow = build_workflow_plan(
                str(perceived_arguments.get("text", ""))
            )

        if desired_workflow is not None and not any(
            item.kind == "workflow_plan"
            and item.content.get("workflow_id")
            == desired_workflow.workflow_id
            for item in items
        ):
            revised_proposals.append(
                WorkspaceItem(
                    source_module=self.name,
                    kind="workflow_plan",
                    content=desired_workflow.model_dump(mode="json"),
                    salience=0.92,
                    confidence=max(0.78, desired_workflow.confidence),
                )
            )

        if desired_action and not any(
            item.kind == "action_suggestion"
            and item.content.get("action") == desired_action
            for item in items
        ):
            revised_proposals.append(
                WorkspaceItem(
                    source_module=self.name,
                    kind="action_suggestion",
                    content={"action": desired_action, "args": desired_args},
                    salience=0.9,
                    confidence=0.95,
                )
            )

        adjustments = []
        strategy_target_map = {
            "memory_persistence_strategy": {"store_note"},
            "artifact_authoring_strategy": {"write_artifact"},
            "workspace_mutation_strategy": {
                "patch_text_file",
                "replace_in_file",
            },
            "investigation_strategy": {"investigate_workspace_issue"},
            "contract_drift_strategy": {
                "search_workspace",
                "read_text_range",
                "summarize_search_results",
            },
            "run_reporting_strategy": {"create_run_report"},
            "workspace_inspection_strategy": {
                "list_dir",
                "glob_workspace",
                "search_workspace",
                "read_text_range",
                "read_file",
                "stat_path",
            },
        }
        for item in items:
            if item.kind != "action_suggestion":
                continue
            action = item.content.get("action")
            delta = 0.0
            reasons: List[str] = []
            if desired_action and action == desired_action:
                delta += 0.12
                reasons.append("perception_alignment")
            elif desired_action and action != desired_action:
                delta -= 0.03
                reasons.append("perception_misalignment")

            if (
                strategy in strategy_target_map
                and action in strategy_target_map[strategy]
            ):
                delta += 0.08
                reasons.append("plan_alignment")

            if critiques:
                delta -= 0.08
                reasons.append("critique")

            if action in {
                "write_artifact",
                "patch_text_file",
                "replace_in_file",
                "run_command",
            } and desired_action != action:
                delta -= 0.2
                reasons.append("proactive_risk")

            if delta != 0.0:
                adjustments.append(
                    {
                        "target_item_id": item.item_id,
                        "delta": delta,
                        "reason": "+".join(reasons),
                    }
                )

        return {
            "revised_proposals": revised_proposals,
            "confidence_adjustments": adjustments,
            "critique_items": [],
        }

    def propose(
        self, input_data: Union[str, List[WorkspaceItem]]
    ) -> ModuleProposal:
        """Select tools based on intent and plan strategy."""

        current_items = input_data if isinstance(input_data, list) else []

        strategy = None
        intent_class = None
        args = {}
        for item in current_items:
            if item.kind == "task_plan":
                strategy = item.content.get("strategy")
            elif item.kind == "perceived_intent":
                intent_class = item.content.get("intent_class")
                args = item.content.get("arguments", {})

        if not intent_class and isinstance(input_data, str):
            run = load_run(input_data)
            goal = run.goal if run else ""
            goal_lower = goal.lower()
            if "note" in goal_lower or "remember" in goal_lower:
                intent_class = "store_note"
                args = {"note": goal}
            else:
                intent_class = "general"
                args = {"text": goal}

        workflow_plan = build_workflow_plan(
            str(args.get("text", args.get("query", "")))
        )

        candidate_items: list[WorkspaceItem] = []
        if workflow_plan is not None:
            candidate_items.append(
                WorkspaceItem(
                    source_module=self.name,
                    kind="workflow_plan",
                    content=workflow_plan.model_dump(mode="json"),
                    salience=0.93,
                    confidence=max(0.8, workflow_plan.confidence),
                )
            )
            action = workflow_plan.steps[0].tool_name
            final_args = resolve_step_arguments(
                workflow_plan,
                workflow_plan.steps[0],
                step_history=[],
            )
            confidence = max(0.8, workflow_plan.confidence)
        else:
            action = "echo"
            final_args = {}

            if intent_class == "store_note":
                action = "store_note"
                final_args = {
                    "note": args.get("text", args.get("note", ""))
                }
            elif intent_class == "retrieve_memory":
                inferred_action, inferred_args = (
                    infer_workspace_action_from_text(
                        str(args.get("query", ""))
                    )
                )
                if inferred_action is not None:
                    action = inferred_action
                    final_args = inferred_args
                else:
                    action = "echo"
                    final_args = {
                        "text": f"Searching for: {args.get('query')}"
                    }
            elif intent_class == "write_artifact":
                action = "write_artifact"
                final_args = args
            elif intent_class == "general":
                inferred_action, inferred_args = (
                    infer_workspace_action_from_text(
                        str(args.get("text", ""))
                    )
                )
                if inferred_action is not None:
                    action = inferred_action
                    final_args = inferred_args
                else:
                    action = "echo"
                    final_args = {"text": args.get("text", "hello")}
            else:
                action = "echo"
                final_args = {"text": args.get("text", "hello")}

            confidence = 1.0
            if strategy in {
                "single_action_dispatch",
                "workspace_inspection_strategy",
            }:
                confidence = 1.0
            elif strategy is None:
                confidence = 0.8

        item = WorkspaceItem(
            source_module=self.name,
            kind="action_suggestion",
            content={"action": action, "args": final_args},
            salience=0.9,
            confidence=confidence,
        )
        candidate_items.append(item)

        return ModuleProposal(
            source_module=self.name,
            candidate_items=candidate_items,
            rationale=(
                f"Selected {action} with confidence {confidence} "
                f"based on strategy {strategy}."
            ),
            confidence=confidence,
        )
