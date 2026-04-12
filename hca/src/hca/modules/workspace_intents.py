"""Shared heuristics for bounded workspace inspection intents."""

from __future__ import annotations

import re
from typing import Dict, Optional, Tuple


_PATH_PATTERNS = (
    r"`([^`]+)`",
    r'"([^"]+)"',
    r"'([^']+)'",
)


def extract_path_hint(text: str) -> Optional[str]:
    for pattern in _PATH_PATTERNS:
        match = re.search(pattern, text)
        if match:
            return match.group(1)

    path_candidates = re.findall(
        r"(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.[A-Za-z0-9_.-]+",
        text,
    )
    if path_candidates:
        return path_candidates[-1]

    if "readme" in text.lower():
        return "README.md"
    return None


def infer_workspace_action_from_text(
    text: str,
) -> Tuple[Optional[str], Dict[str, str]]:
    goal_lower = text.lower()

    if any(
        phrase in goal_lower
        for phrase in (
            "list files",
            "list file",
            "list directory",
            "show directory",
            "show files",
            "inspect repository",
            "inspect repo",
        )
    ):
        return "list_dir", {"path": "."}

    if any(
        phrase in goal_lower
        for phrase in (
            "read file",
            "show file",
            "open file",
            "inspect file",
        )
    ):
        path_hint = extract_path_hint(text)
        if path_hint:
            return "read_file", {"path": path_hint}

    return None, {}
