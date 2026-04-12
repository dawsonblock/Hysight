"""Shared heuristics for bounded workspace inspection intents."""

from __future__ import annotations

import re
from typing import Any, Dict, Optional, Tuple


_QUOTED_SEGMENTS = re.compile(r"[`\"']([^`\"']+)[`\"']")


def _quoted_segments(text: str) -> list[str]:
    return [match.group(1) for match in _QUOTED_SEGMENTS.finditer(text)]


def _looks_like_path(value: str) -> bool:
    return "/" in value or bool(
        re.search(r"\.[A-Za-z0-9_.-]+$", value)
    )


def extract_path_hint(text: str) -> Optional[str]:
    path_candidates = re.findall(
        r"(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.[A-Za-z0-9_.-]+",
        text,
    )
    if path_candidates:
        return path_candidates[-1]

    quoted_paths = [
        segment
        for segment in _quoted_segments(text)
        if _looks_like_path(segment)
    ]
    if quoted_paths:
        return quoted_paths[-1]

    if "readme" in text.lower():
        return "README.md"
    return None


def extract_search_query(text: str) -> Optional[str]:
    path_hint = extract_path_hint(text)
    for segment in _quoted_segments(text):
        if segment != path_hint and not _looks_like_path(segment):
            return segment

    match = re.search(
        r"(?:search for|find text|look for|search)\s+(.+?)(?:\s+in\s+.+)?$",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    return match.group(1).strip(" .") or None


def extract_glob_pattern(text: str) -> Optional[str]:
    for segment in _quoted_segments(text):
        if "*" in segment or "?" in segment:
            return segment
    return None


def extract_line_range(text: str) -> Optional[Tuple[int, int]]:
    match = re.search(
        r"lines?\s+(\d+)\s*(?:-|to)\s*(\d+)",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    start_line = int(match.group(1))
    end_line = int(match.group(2))
    if end_line < start_line:
        start_line, end_line = end_line, start_line
    return start_line, end_line


def extract_replace_directive(
    text: str,
) -> Optional[Tuple[str, str, str]]:
    match = re.search(
        (
            r"replace\s+[`\"']([^`\"']+)[`\"']\s+with\s+"
            r"[`\"']([^`\"']*)[`\"']\s+in\s+"
            r"[`\"']([^`\"']+)[`\"']"
        ),
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    return match.group(3), match.group(1), match.group(2)


def infer_workspace_action_from_text(
    text: str,
) -> Tuple[Optional[str], Dict[str, Any]]:
    goal_lower = text.lower()

    replace_directive = extract_replace_directive(text)
    if replace_directive is not None:
        path, old_text, new_text = replace_directive
        return (
            "patch_text_file",
            {
                "path": path,
                "old_text": old_text,
                "new_text": new_text,
                "apply": True,
            },
        )

    if any(
        phrase in goal_lower
        for phrase in (
            "investigate contract mismatch",
            "inspect contract mismatch",
            "investigate api mismatch",
            "inspect api mismatch",
            "schema mismatch",
            "interface mismatch",
        )
    ):
        query = extract_search_query(text)
        if query:
            search_args: Dict[str, Any] = {"query": query}
            path_hint = extract_path_hint(text)
            if path_hint:
                search_args["path_glob"] = path_hint
            return "investigate_workspace_issue", search_args

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
            "find files matching",
            "glob",
            "match files",
        )
    ):
        pattern = extract_glob_pattern(text) or "**/*"
        return "glob_workspace", {"pattern": pattern}

    if any(
        phrase in goal_lower
        for phrase in (
            "stat path",
            "path info",
            "file info",
            "inspect path",
        )
    ):
        return "stat_path", {"path": extract_path_hint(text) or "."}

    if "cargo test" in goal_lower:
        return "run_command", {"argv": ["cargo", "test"]}

    if "cargo check" in goal_lower:
        return "run_command", {"argv": ["cargo", "check"]}

    if any(
        phrase in goal_lower
        for phrase in (
            "run tests",
            "run test",
            "run pytest",
            "pytest",
        )
    ):
        return "run_command", {"argv": ["pytest", "-q"]}

    if any(
        phrase in goal_lower
        for phrase in (
            "search workspace",
            "search repo",
            "search repository",
            "search for",
            "find text",
            "look for",
        )
    ):
        query = extract_search_query(text)
        if query:
            args: Dict[str, Any] = {"query": query}
            path_hint = extract_path_hint(text)
            if path_hint:
                args["path_glob"] = path_hint
            return "search_workspace", args

    if any(
        phrase in goal_lower
        for phrase in (
            "create run report",
            "create report",
            "emit report",
            "summarize this run",
            "run summary",
        )
    ):
        return "create_run_report", {}

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
            line_range = extract_line_range(text)
            range_args: Dict[str, Any] = {"path": path_hint}
            if line_range is not None:
                (
                    range_args["start_line"],
                    range_args["end_line"],
                ) = line_range
            return "read_text_range", range_args

    return None, {}
