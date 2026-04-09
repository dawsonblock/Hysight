"""Deterministic evaluation case definitions for the v5 harnesses."""

from __future__ import annotations

from typing import Any

from hca.common.enums import ControlSignal


COORDINATION_CASES: list[dict[str, Any]] = [
    {
        "name": "greeting_dispatch",
        "goal": "hi there",
        "expected_action": "echo",
        "requires_approval": False,
    },
    {
        "name": "memory_write_dispatch",
        "goal": "remember to buy milk",
        "expected_action": "store_note",
        "requires_approval": True,
    },
]


METACOGNITION_CASES: list[dict[str, Any]] = [
    {
        "name": "clean_workspace",
        "scenario": "clean",
        "expected": ControlSignal.proceed,
    },
    {
        "name": "contradictory_memory",
        "scenario": "contradiction",
        "expected": ControlSignal.replan,
    },
    {
        "name": "missing_required_input",
        "scenario": "missing_info",
        "expected": ControlSignal.ask_user,
    },
    {
        "name": "unsupported_tool",
        "scenario": "unsupported",
        "expected": ControlSignal.halt,
    },
]


PROACTIVITY_CASES: list[dict[str, Any]] = [
    {
        "name": "proactive_write_blocked",
        "action": "write_artifact",
        "args": {"content": "draft"},
        "expected": ControlSignal.require_approval,
    },
    {
        "name": "proactive_echo_allowed",
        "action": "echo",
        "args": {"text": "status"},
        "expected": ControlSignal.proceed,
    },
]


EMBODIMENT_CASES: list[dict[str, Any]] = [
    {
        "name": "artifact_creation",
        "goal": "write file with project summary",
        "expected_action": "write_artifact",
        "requires_approval": True,
    }
]
