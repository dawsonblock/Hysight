#!/usr/bin/env python3
"""Write machine-readable proof receipts for optional proof surfaces."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RECEIPT_DIR = REPO_ROOT / "test_reports" / "proof_receipts"


def _junit_counts(junit_xml: Path | None) -> tuple[Dict[str, int], str | None]:
    counts = {
        "total_test_count": 0,
        "passed_test_count": 0,
        "skipped_test_count": 0,
        "failed_test_count": 0,
        "error_test_count": 0,
    }
    if junit_xml is None or not junit_xml.exists():
        return counts, None

    try:
        root = ET.parse(junit_xml).getroot()
    except ET.ParseError as exc:
        return counts, f"invalid junit xml: {exc}"

    tests = int(root.attrib.get("tests", 0))
    skipped = int(root.attrib.get("skipped", 0))
    failures = int(root.attrib.get("failures", 0))
    errors = int(root.attrib.get("errors", 0))
    counts["total_test_count"] = tests
    counts["skipped_test_count"] = skipped
    counts["failed_test_count"] = failures
    counts["error_test_count"] = errors
    counts["passed_test_count"] = max(tests - skipped - failures - errors, 0)
    return counts, None


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


def write_proof_receipt(
    *,
    output_path: Path,
    proof_tier: str,
    environment_mode: str,
    service_connection_mode: str,
    service_endpoint: str,
    command: str,
    junit_xml: Path | None = None,
    outcome: str,
    failure_reason: str | None = None,
    metadata: Dict[str, Any] | None = None,
) -> Path:
    counts, junit_error = _junit_counts(junit_xml)
    receipt = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "commit_sha": _resolve_commit_sha(),
        "proof_tier": proof_tier,
        "environment_mode": environment_mode,
        "service_connection_mode": service_connection_mode,
        "service_endpoint": service_endpoint,
        "command": command,
        "outcome": outcome,
        **counts,
        "junit_xml": (
            str(junit_xml.relative_to(REPO_ROOT))
            if junit_xml is not None and junit_xml.exists()
            else None
        ),
    }
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
    parser.add_argument("--outcome", required=True)
    parser.add_argument("--failure-reason")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    output_path = write_proof_receipt(
        output_path=args.output,
        proof_tier=args.proof_tier,
        environment_mode=args.environment_mode,
        service_connection_mode=args.service_connection_mode,
        service_endpoint=args.service_endpoint,
        command=args.command,
        junit_xml=args.junit_xml,
        outcome=args.outcome,
        failure_reason=args.failure_reason,
    )
    print(output_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())