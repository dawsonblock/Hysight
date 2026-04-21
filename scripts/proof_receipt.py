#!/usr/bin/env python3
"""Write machine-readable proof receipts for Hysight proof surfaces."""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RECEIPT_DIR = REPO_ROOT / "artifacts" / "proof"

COUNT_KEYS = (
    "total_test_count",
    "passed_test_count",
    "skipped_test_count",
    "failed_test_count",
    "error_test_count",
)


def empty_test_counts() -> Dict[str, int]:
    return {key: 0 for key in COUNT_KEYS}


def merge_test_counts(*counts_list: Iterable[Dict[str, int]]) -> Dict[str, int]:
    merged = empty_test_counts()
    for counts in counts_list:
        for key in COUNT_KEYS:
            merged[key] += int(counts.get(key, 0))
    return merged


def _strip_xml_namespace(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def summarize_junit_xml(
    junit_xml: Path | None,
) -> tuple[Dict[str, int], List[Dict[str, str]], str | None]:
    counts = empty_test_counts()
    skipped_cases: List[Dict[str, str]] = []
    if junit_xml is None or not junit_xml.exists():
        return counts, skipped_cases, None

    try:
        root = ET.parse(junit_xml).getroot()
    except ET.ParseError as exc:
        return counts, skipped_cases, f"invalid junit xml: {exc}"

    testcases = [
        testcase
        for testcase in root.iter()
        if _strip_xml_namespace(testcase.tag) == "testcase"
    ]
    if not testcases:
        tests = int(root.attrib.get("tests", 0))
        skipped = int(root.attrib.get("skipped", 0))
        failures = int(root.attrib.get("failures", 0))
        errors = int(root.attrib.get("errors", 0))
        counts["total_test_count"] = tests
        counts["skipped_test_count"] = skipped
        counts["failed_test_count"] = failures
        counts["error_test_count"] = errors
        counts["passed_test_count"] = max(tests - skipped - failures - errors, 0)
        return counts, skipped_cases, None

    counts["total_test_count"] = len(testcases)
    for testcase in testcases:
        outcome = None
        for child in list(testcase):
            child_tag = _strip_xml_namespace(child.tag)
            if child_tag == "skipped":
                counts["skipped_test_count"] += 1
                skipped_cases.append(
                    {
                        "classname": testcase.attrib.get("classname", ""),
                        "name": testcase.attrib.get("name", ""),
                        "message": child.attrib.get("message", "")
                        or (child.text or "").strip(),
                    }
                )
                outcome = "skipped"
                break
            if child_tag == "failure":
                counts["failed_test_count"] += 1
                outcome = "failed"
                break
            if child_tag == "error":
                counts["error_test_count"] += 1
                outcome = "error"
                break
        if outcome is None:
            counts["passed_test_count"] += 1

    return counts, skipped_cases, None


def _resolve_commit_sha() -> str:
    for key in ("GITHUB_SHA", "COMMIT_SHA", "BUILD_VCS_NUMBER"):
        value = os.environ.get(key, "").strip()
        if value:
            return value

    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
    except Exception:
        return "local-worktree"

    return result.stdout.strip() or "local-worktree"


def _resolve_repo_fingerprint() -> str | None:
    try:
        result = subprocess.run(
            ["sh", "-c", "find . -type f | sort | shasum | shasum | awk '{print $1}'"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
    except Exception:
        return None

    fingerprint = result.stdout.strip()
    return fingerprint or None


def write_proof_receipt(
    *,
    output_path: Path,
    proof_tier: str,
    environment_mode: str,
    service_connection_mode: str,
    service_endpoint: str,
    command: str,
    junit_xml: Path | None = None,
    counts: Dict[str, int] | None = None,
    outcome: str,
    failure_reason: str | None = None,
    metadata: Dict[str, Any] | None = None,
) -> Path:
    resolved_counts = counts or empty_test_counts()
    skipped_cases: List[Dict[str, str]] = []
    junit_error = None
    if counts is None:
        resolved_counts, skipped_cases, junit_error = summarize_junit_xml(junit_xml)

    timestamp = datetime.now(timezone.utc).isoformat()
    receipt = {
        "schema_version": 2,
        "timestamp": timestamp,
        "generated_at": timestamp,
        "commit_sha": _resolve_commit_sha(),
        "repo_fingerprint": _resolve_repo_fingerprint(),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "proof_tier": proof_tier,
        "environment_mode": environment_mode,
        "service_connection_mode": service_connection_mode,
        "service_endpoint": service_endpoint,
        "command": command,
        "outcome": outcome,
        **resolved_counts,
        "junit_xml": (
            str(junit_xml.relative_to(REPO_ROOT))
            if junit_xml is not None and junit_xml.exists()
            else None
        ),
    }
    if skipped_cases:
        receipt["skipped_cases"] = skipped_cases
    if failure_reason:
        receipt["failure_reason"] = failure_reason
    if junit_error:
        receipt["junit_summary_error"] = junit_error
    if metadata:
        receipt["metadata"] = metadata

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--proof-tier", required=True)
    parser.add_argument("--environment-mode", required=True)
    parser.add_argument("--service-connection-mode", required=True)
    parser.add_argument("--service-endpoint", required=True)
    parser.add_argument("--command", required=True)
    parser.add_argument("--junit-xml", type=Path)
    parser.add_argument("--counts-json")
    parser.add_argument("--outcome", required=True)
    parser.add_argument("--failure-reason")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    counts = None
    if args.counts_json:
        counts = json.loads(args.counts_json)
    output_path = write_proof_receipt(
        output_path=args.output,
        proof_tier=args.proof_tier,
        environment_mode=args.environment_mode,
        service_connection_mode=args.service_connection_mode,
        service_endpoint=args.service_endpoint,
        command=args.command,
        junit_xml=args.junit_xml,
        counts=counts,
        outcome=args.outcome,
        failure_reason=args.failure_reason,
    )
    print(output_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())