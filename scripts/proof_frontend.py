#!/usr/bin/env python3
"""Run the frontend proof surface and write a machine-readable receipt."""

from __future__ import annotations

import json
import os
import pathlib
import shlex
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Sequence

try:
    from proof_receipt import (
        empty_test_counts,
        merge_test_counts,
        summarize_junit_xml,
        write_proof_receipt,
    )
except ModuleNotFoundError:  # pragma: no cover - package import fallback
    from scripts.proof_receipt import (
        empty_test_counts,
        merge_test_counts,
        summarize_junit_xml,
        write_proof_receipt,
    )


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
FRONTEND_ROOT = REPO_ROOT / "frontend"
PROOF_RECEIPT_PATH = REPO_ROOT / "artifacts" / "proof" / "frontend.json"
JEST_REPORT_PATH = REPO_ROOT / "test_reports" / "frontend-jest.json"
FIXTURE_JUNIT_PATH = REPO_ROOT / "test_reports" / "frontend-fixture-drift.xml"
EXPECTED_NODE_MAJOR = 24
EXPECTED_YARN_VERSION = "1.22.22"
REPO_VENV_DIR = (REPO_ROOT / ".venv").resolve()
ALL_PROOF_STEP_IDS = (
    "pipeline",
    "backend-baseline",
    "contract",
    "frontend",
    "integration",
    "mongo-live",
    "sidecar",
)


class FrontendProofError(RuntimeError):
    """Raised when the frontend proof surface cannot complete."""


def _tail_text(text: str, *, lines: int = 20) -> str | None:
    stripped = text.strip()
    if not stripped:
        return None
    return "\n".join(stripped.splitlines()[-lines:])


def _command_string(command: Sequence[str]) -> str:
    return shlex.join(list(command))


def _env_mode() -> str:
    python_mode = (
        "repo_local_venv"
        if pathlib.Path(sys.prefix).resolve() == REPO_VENV_DIR
        else "external_python"
    )
    return f"{python_mode}+local_node"


def _run_command(
    *,
    name: str,
    command: Sequence[str],
    cwd: pathlib.Path,
    env: Dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    print(f"\n==> [{name}]")
    print(f"    {_command_string(command)}")
    completed = subprocess.run(
        list(command),
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.stdout:
        print(completed.stdout, end="")
    if completed.stderr:
        print(completed.stderr, end="", file=sys.stderr)
    return completed


def _require_tool(command: str) -> None:
    if not shutil.which(command):
        raise FrontendProofError(
            f"{command} is unavailable. Use Node {EXPECTED_NODE_MAJOR}.x and "
            f"Yarn {EXPECTED_YARN_VERSION}, then run make test-bootstrap-frontend."
        )


def _parse_node_major(version_text: str) -> int | None:
    stripped = version_text.strip().lstrip("v")
    major_text = stripped.split(".", 1)[0]
    try:
        return int(major_text)
    except ValueError:
        return None


def _validate_runtime(stage_results: List[Dict[str, Any]]) -> tuple[str, str]:
    node_version_result = _run_command(
        name="Node version",
        command=["node", "--version"],
        cwd=FRONTEND_ROOT,
    )
    if node_version_result.returncode != 0:
        raise FrontendProofError("Unable to determine the Node.js version.")
    node_version = node_version_result.stdout.strip()
    node_major = _parse_node_major(node_version)
    if node_major != EXPECTED_NODE_MAJOR:
        stage_results.append(
            {
                "name": "runtime-verification",
                "command": _command_string(["node", "--version"]),
                "returncode": node_version_result.returncode,
                "status": "failed",
                "node_version": node_version,
                "yarn_version": "unknown",
                "stdout_tail": _tail_text(node_version_result.stdout),
                "stderr_tail": _tail_text(node_version_result.stderr),
            }
        )
        raise FrontendProofError(
            f"Hysight frontend requires Node {EXPECTED_NODE_MAJOR}.x. "
            f"Detected Node {node_version}."
        )

    yarn_version_result = _run_command(
        name="Yarn version",
        command=["yarn", "--version"],
        cwd=FRONTEND_ROOT,
    )
    if yarn_version_result.returncode != 0:
        stage_results.append(
            {
                "name": "runtime-verification",
                "command": _command_string(["yarn", "--version"]),
                "returncode": yarn_version_result.returncode,
                "status": "failed",
                "node_version": node_version,
                "yarn_version": "unknown",
                "stdout_tail": _tail_text(yarn_version_result.stdout),
                "stderr_tail": _tail_text(yarn_version_result.stderr),
            }
        )
        raise FrontendProofError("Unable to determine the Yarn version.")
    yarn_version = yarn_version_result.stdout.strip()
    if yarn_version != EXPECTED_YARN_VERSION:
        stage_results.append(
            {
                "name": "runtime-verification",
                "command": _command_string(["yarn", "--version"]),
                "returncode": yarn_version_result.returncode,
                "status": "failed",
                "node_version": node_version,
                "yarn_version": yarn_version,
                "stdout_tail": _tail_text(yarn_version_result.stdout),
                "stderr_tail": _tail_text(yarn_version_result.stderr),
            }
        )
        raise FrontendProofError(
            f"Hysight frontend requires Yarn {EXPECTED_YARN_VERSION}. "
            f"Detected Yarn {yarn_version}."
        )

    runtime_env = dict(os.environ)
    runtime_env["npm_config_user_agent"] = (
        f"yarn/{yarn_version} npm/? node/{node_version.lstrip('v')} darwin arm64"
    )
    runtime_check = _run_command(
        name="Frontend runtime verification",
        command=["node", "./scripts/verify-runtime.js"],
        cwd=FRONTEND_ROOT,
        env=runtime_env,
    )
    stage_results.append(
        {
            "name": "runtime-verification",
            "command": _command_string(["node", "./scripts/verify-runtime.js"]),
            "returncode": runtime_check.returncode,
            "status": "passed" if runtime_check.returncode == 0 else "failed",
            "node_version": node_version,
            "yarn_version": yarn_version,
            "stdout_tail": _tail_text(runtime_check.stdout),
            "stderr_tail": _tail_text(runtime_check.stderr),
        }
    )
    if runtime_check.returncode != 0:
        raise FrontendProofError(
            "Frontend runtime verification failed. Use Node 24.15.0 and Yarn 1.22.22."
        )
    return node_version, yarn_version


def _proof_scope_metadata(
    stage_results: List[Dict[str, Any]],
    skipped_cases: List[Dict[str, str]],
    *,
    node_version: str,
    yarn_version: str,
) -> Dict[str, Any]:
    covered_stage_names = [str(stage.get("name", "")) for stage in stage_results]
    passed_stage_names = [
        str(stage.get("name", ""))
        for stage in stage_results
        if stage.get("status") == "passed"
    ]
    failed_stage_names = [
        str(stage.get("name", ""))
        for stage in stage_results
        if stage.get("status") == "failed"
    ]

    return {
        "receipt_scope": (
            "This receipt covers only the frontend proof and the stages "
            "listed in covered_stage_names."
        ),
        "covered_proof_steps": ["frontend"],
        "omitted_proof_steps": [
            step_id for step_id in ALL_PROOF_STEP_IDS if step_id != "frontend"
        ],
        "covered_stage_names": covered_stage_names,
        "passed_stage_names": passed_stage_names,
        "failed_stage_names": failed_stage_names,
        "node_version": node_version,
        "yarn_version": yarn_version,
        "stages": stage_results,
        "receipt_format": "frontend-proof-v1",
        "skipped_cases": skipped_cases,
    }


def _require_installed_dependencies() -> None:
    sentinels = [
        FRONTEND_ROOT / "node_modules" / ".bin" / "craco",
        FRONTEND_ROOT / "node_modules" / ".bin" / "craco.cmd",
        FRONTEND_ROOT / "node_modules" / "react-scripts" / "package.json",
    ]
    if not any(path.exists() for path in sentinels):
        raise FrontendProofError(
            "Frontend dependencies are not installed. Run make test-bootstrap-frontend "
            "or cd frontend && yarn install --frozen-lockfile."
        )


def _parse_jest_counts(
    report_path: pathlib.Path,
) -> tuple[Dict[str, int], List[Dict[str, str]], Dict[str, Any]]:
    counts = empty_test_counts()
    if not report_path.exists():
        raise FrontendProofError(
            f"Jest report was not written to {report_path.relative_to(REPO_ROOT)}."
        )

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    counts["total_test_count"] = int(payload.get("numTotalTests", 0))
    counts["passed_test_count"] = int(payload.get("numPassedTests", 0))
    counts["skipped_test_count"] = int(payload.get("numPendingTests", 0)) + int(
        payload.get("numTodoTests", 0)
    )
    counts["failed_test_count"] = int(payload.get("numFailedTests", 0))
    counts["error_test_count"] = int(payload.get("numRuntimeErrorTestSuites", 0))

    skipped_cases: List[Dict[str, str]] = []
    for suite in payload.get("testResults", []):
        suite_name = suite.get("name", "")
        for assertion in suite.get("assertionResults", []):
            status = assertion.get("status")
            if status not in {"pending", "todo"}:
                continue
            skipped_cases.append(
                {
                    "classname": suite_name,
                    "name": assertion.get("fullName") or assertion.get("title") or "",
                    "message": status,
                }
            )

    metadata = {
        "num_total_test_suites": int(payload.get("numTotalTestSuites", 0)),
        "num_passed_test_suites": int(payload.get("numPassedTestSuites", 0)),
        "num_failed_test_suites": int(payload.get("numFailedTestSuites", 0)),
        "num_runtime_error_test_suites": int(payload.get("numRuntimeErrorTestSuites", 0)),
        "success": bool(payload.get("success", False)),
    }
    return counts, skipped_cases, metadata


def main() -> int:
    stage_results: List[Dict[str, Any]] = []
    counts = empty_test_counts()
    skipped_cases: List[Dict[str, str]] = []
    failure_reason: str | None = None
    outcome = "failed"
    node_version = "unknown"
    yarn_version = "unknown"

    PROOF_RECEIPT_PATH.parent.mkdir(parents=True, exist_ok=True)
    JEST_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE_JUNIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROOF_RECEIPT_PATH.unlink(missing_ok=True)
    JEST_REPORT_PATH.unlink(missing_ok=True)
    FIXTURE_JUNIT_PATH.unlink(missing_ok=True)

    try:
        _require_tool("node")
        _require_tool("yarn")
        node_version, yarn_version = _validate_runtime(stage_results)
        _require_installed_dependencies()

        fixture_command = [
            sys.executable,
            "-m",
            "pytest",
            "backend/tests/test_server_bootstrap.py",
            "-q",
            "--check-fixture-drift",
            "-k",
            "generated_frontend_api_fixtures_match_backend_export",
            "-ra",
            "--strict-markers",
            f"--junitxml={FIXTURE_JUNIT_PATH}",
        ]
        fixture_result = _run_command(
            name="Frontend fixture drift gate",
            command=fixture_command,
            cwd=REPO_ROOT,
        )
        fixture_counts, fixture_skipped, fixture_junit_error = summarize_junit_xml(
            FIXTURE_JUNIT_PATH if FIXTURE_JUNIT_PATH.exists() else None
        )
        stage_results.append(
            {
                "name": "fixture-drift",
                "command": _command_string(fixture_command),
                "returncode": fixture_result.returncode,
                "status": "passed" if fixture_result.returncode == 0 else "failed",
                "counts": fixture_counts,
                "junit_xml": str(FIXTURE_JUNIT_PATH.relative_to(REPO_ROOT))
                if FIXTURE_JUNIT_PATH.exists()
                else None,
                "junit_error": fixture_junit_error,
                "stdout_tail": _tail_text(fixture_result.stdout),
                "stderr_tail": _tail_text(fixture_result.stderr),
            }
        )
        counts = merge_test_counts(counts, fixture_counts)
        skipped_cases.extend(fixture_skipped)
        if fixture_result.returncode != 0:
            raise FrontendProofError("Frontend fixture drift gate failed.")

        lint_command = ["yarn", "lint"]
        lint_result = _run_command(
            name="Frontend lint",
            command=lint_command,
            cwd=FRONTEND_ROOT,
        )
        stage_results.append(
            {
                "name": "lint",
                "command": _command_string(lint_command),
                "returncode": lint_result.returncode,
                "status": "passed" if lint_result.returncode == 0 else "failed",
                "stdout_tail": _tail_text(lint_result.stdout),
                "stderr_tail": _tail_text(lint_result.stderr),
            }
        )
        if lint_result.returncode != 0:
            raise FrontendProofError("Frontend lint failed.")

        jest_command = [
            "yarn",
            "test",
            "--watch=false",
            "--runInBand",
            "--json",
            f"--outputFile={JEST_REPORT_PATH}",
        ]
        jest_env = dict(os.environ)
        jest_env["CI"] = "true"
        jest_result = _run_command(
            name="Frontend tests",
            command=jest_command,
            cwd=FRONTEND_ROOT,
            env=jest_env,
        )
        jest_counts, jest_skipped, jest_metadata = _parse_jest_counts(JEST_REPORT_PATH)
        stage_results.append(
            {
                "name": "jest",
                "command": _command_string(jest_command),
                "returncode": jest_result.returncode,
                "status": "passed" if jest_result.returncode == 0 else "failed",
                "counts": jest_counts,
                "report": str(JEST_REPORT_PATH.relative_to(REPO_ROOT)),
                "metadata": jest_metadata,
                "stdout_tail": _tail_text(jest_result.stdout),
                "stderr_tail": _tail_text(jest_result.stderr),
            }
        )
        counts = merge_test_counts(counts, jest_counts)
        skipped_cases.extend(jest_skipped)
        if jest_result.returncode != 0:
            raise FrontendProofError("Frontend tests failed.")

        build_command = ["yarn", "build"]
        build_result = _run_command(
            name="Frontend build",
            command=build_command,
            cwd=FRONTEND_ROOT,
        )
        stage_results.append(
            {
                "name": "build",
                "command": _command_string(build_command),
                "returncode": build_result.returncode,
                "status": "passed" if build_result.returncode == 0 else "failed",
                "stdout_tail": _tail_text(build_result.stdout),
                "stderr_tail": _tail_text(build_result.stderr),
            }
        )
        if build_result.returncode != 0:
            raise FrontendProofError("Frontend build failed.")

        outcome = "passed"
        print(
            "\nFrontend proof passed "
            f"({counts['passed_test_count']} passed, {counts['skipped_test_count']} skipped)."
        )
        return 0
    except FrontendProofError as exc:
        failure_reason = str(exc)
        print(f"\nFAILED: {failure_reason}", file=sys.stderr)
        return 1
    finally:
        if node_version == "unknown":
            for stage in reversed(stage_results):
                candidate = stage.get("node_version")
                if candidate:
                    node_version = str(candidate)
                    break
        if yarn_version == "unknown":
            for stage in reversed(stage_results):
                candidate = stage.get("yarn_version")
                if candidate and candidate != "unknown":
                    yarn_version = str(candidate)
                    break
        write_proof_receipt(
            output_path=PROOF_RECEIPT_PATH,
            proof_tier="frontend",
            environment_mode=_env_mode(),
            service_connection_mode="none",
            service_endpoint="n/a",
            command=_command_string([sys.executable, *sys.argv]),
            counts=counts,
            outcome=outcome,
            failure_reason=failure_reason,
            metadata=_proof_scope_metadata(
                stage_results,
                skipped_cases,
                node_version=node_version,
                yarn_version=yarn_version,
            ),
        )


if __name__ == "__main__":
    sys.exit(main())