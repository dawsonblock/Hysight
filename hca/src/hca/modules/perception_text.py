"""Perception module for textual inputs."""

from typing import List, Union
from hca.common.types import ModuleProposal, WorkspaceItem
from hca.storage import load_run

class TextPerception:
    name = "perception_text"

    def update(self, items: List[WorkspaceItem]) -> None:
        """Update internal state based on workspace content."""
        pass

    def propose(self, input_data: Union[str, List[WorkspaceItem]]) -> ModuleProposal:
        if isinstance(input_data, list):
            # Already have intent in workspace?
            for item in input_data:
                if item.kind == "perceived_intent":
                    return ModuleProposal(source_module=self.name, candidate_items=[], rationale="Intent already perceived.")
            return ModuleProposal(source_module=self.name, candidate_items=[], rationale="No new intent to perceive.")
            
        # Read real run goal
        run = load_run(input_data)
        goal = run.goal if run else ""
        
        # Grounded interpretation (simple rule-based)
        goal_lower = goal.lower()
        
        intent_class = "general"
        intent = "general"
        args = {}
        
        if "note" in goal_lower or "remember" in goal_lower:
            intent_class = "store_note"
            intent = "store"
            # Simple extraction: everything after "note" or "remember"
            for keyword in ["note ", "remember "]:
                if keyword in goal_lower:
                    args["text"] = goal[goal_lower.find(keyword) + len(keyword):].strip()
                    break
            if not args.get("text"):
                args["text"] = goal
        elif "retrieve" in goal_lower or "find" in goal_lower:
            intent_class = "retrieve_memory"
            intent = "retrieve"
            args["query"] = goal
        elif "artifact" in goal_lower or "write file" in goal_lower:
            intent_class = "write_artifact"
            args["content"] = goal
            args["path"] = "output.txt"
        elif "hello" in goal_lower or "hi" in goal_lower:
            intent_class = "greeting"
            args["text"] = "hello"
        
        item = WorkspaceItem(
            source_module=self.name,
            kind="perceived_intent",
            content={
                "raw_goal": goal,
                "intent_class": intent_class,
                "intent": intent,
                "arguments": args
            },
            salience=0.8,
            confidence=1.0
        )
        
        return ModuleProposal(
            source_module=self.name,
            candidate_items=[item],
            rationale=f"Interpreted goal as {intent_class}",
            confidence=1.0
        )
