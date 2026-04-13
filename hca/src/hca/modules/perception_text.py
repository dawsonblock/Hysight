"""TextPerception module — LLM-powered intent classification via
Gemini 3 Flash.

Falls back to rule-based classification if the LLM call fails.
"""
from __future__ import annotations

import asyncio
import json
import os
import uuid
from typing import List, Union

from hca.common.types import ModuleProposal, WorkspaceItem
from hca.storage import load_run

_SYSTEM_PROMPT = """\
You are the TextPerception module of a Hybrid Cognitive Agent. \
Classify the user's goal into a structured intent.

Intent classes:
  store_note      — user wants to remember / save / note something
  retrieve_memory — user wants to find / recall / search something
  write_artifact  — user wants to create / write a file or document
  greeting        — simple greeting (hello, hi, hey)
  general         — anything else

Respond ONLY with valid JSON — no markdown fences:
{
  "intent_class": "<class>",
  "intent": "<store|retrieve|write|general>",
  "arguments": {"<extracted_key>": "<extracted_value>"},
  "confidence": 0.9
}"""

_INTENT_MAP = {
    "store_note": "store",
    "retrieve_memory": "retrieve",
    "write_artifact": "write",
    "greeting": "general",
    "general": "general",
}


async def _llm_perceive(goal: str) -> dict:
    from emergentintegrations.llm.chat import (  # type: ignore
        LlmChat,
        UserMessage,
    )

    api_key = os.environ.get("EMERGENT_LLM_KEY", "")
    chat = LlmChat(
        api_key=api_key,
        session_id=f"perception-{uuid.uuid4().hex[:8]}",
        system_message=_SYSTEM_PROMPT,
    ).with_model("gemini", "gemini-3-flash-preview")

    response = await chat.send_message(UserMessage(text=f"Goal: {goal}"))
    text = response.strip()
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1] if len(parts) > 1 else text
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


def _rule_based_perceive(goal: str) -> dict:
    goal_lower = goal.lower()
    if any(k in goal_lower for k in ("note ", "remember ", "save ")):
        return {
            "intent_class": "store_note",
            "intent": "store",
            "arguments": {"text": goal},
            "confidence": 0.6,
        }
    if any(
        k in goal_lower for k in ("retrieve ", "find ", "search ", "recall ")
    ):
        return {
            "intent_class": "retrieve_memory",
            "intent": "retrieve",
            "arguments": {"query": goal},
            "confidence": 0.6,
        }
    if any(k in goal_lower for k in ("write file", "artifact", "create file")):
        return {
            "intent_class": "write_artifact",
            "intent": "write",
            "arguments": {"content": goal, "path": "output.txt"},
            "confidence": 0.6,
        }
    if any(k in goal_lower for k in ("hello", "hi ", "hey ")):
        return {
            "intent_class": "greeting",
            "intent": "general",
            "arguments": {"text": "hello"},
            "confidence": 0.9,
        }
    return {
        "intent_class": "general",
        "intent": "general",
        "arguments": {"text": goal},
        "confidence": 0.5,
    }


class TextPerception:
    name = "perception_text"

    def update(self, items: List[WorkspaceItem]) -> None:
        pass

    def on_broadcast(self, items: List[WorkspaceItem]):
        return {
            "revised_proposals": [],
            "confidence_adjustments": [],
            "critique_items": [],
        }

    def propose(
        self,
        input_data: Union[str, List[WorkspaceItem]],
    ) -> ModuleProposal:
        if isinstance(input_data, list):
            for item in input_data:
                if item.kind == "perceived_intent":
                    return ModuleProposal(
                        source_module=self.name,
                        candidate_items=[],
                        rationale="Intent already perceived.",
                    )
            return ModuleProposal(
                source_module=self.name,
                candidate_items=[],
                rationale="No new intent to perceive.",
            )

        run = load_run(input_data)
        goal = run.goal if run else ""

        perception = None
        perception_mode = "rule_based_only"
        fallback_reason = None
        llm_attempted = False
        if goal:
            llm_attempted = True
            try:
                perception = asyncio.run(_llm_perceive(goal))
                perception_mode = "llm"
            except Exception as exc:
                fallback_reason = f"llm_error:{exc.__class__.__name__}"

        if not perception:
            perception = _rule_based_perceive(goal)
            perception_mode = (
                "rule_based_fallback" if llm_attempted else "rule_based_only"
            )
            if fallback_reason is None and not goal:
                fallback_reason = "missing_goal"

        intent_class = perception.get("intent_class", "general")
        intent = perception.get("intent") or _INTENT_MAP.get(
            intent_class,
            "general",
        )

        item = WorkspaceItem(
            source_module=self.name,
            kind="perceived_intent",
            content={
                "raw_goal": goal,
                "intent_class": intent_class,
                "intent": intent,
                "arguments": perception.get("arguments", {}),
                "perception_mode": perception_mode,
                "fallback_reason": fallback_reason,
                "llm_attempted": llm_attempted,
            },
            salience=0.8,
            confidence=perception.get("confidence", 0.8),
        )

        return ModuleProposal(
            source_module=self.name,
            candidate_items=[item],
            rationale=f"Gemini classified goal as {intent_class}.",
            confidence=perception.get("confidence", 0.8),
        )
