#!/usr/bin/env python3
"""Single proof authority for Hysight.

Default mode runs only the supported service-free local baseline proof surface:

    python scripts/run_tests.py

Optional proof tiers are explicit and do not broaden the baseline contract:

    python scripts/run_tests.py --frontend

    python scripts/run_tests.py --integration

    MONGO_URL=mongodb://127.0.0.1:27017 \
    DB_NAME=hysight_live \
    python scripts/run_tests.py --mongo-live

    MEMORY_SERVICE_PORT=3032 \
    python scripts/run_tests.py --sidecar
"""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
import os
import pathlib
import re
import shlex
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from typing import Any, Dict, List, Sequence

try:
    from proof_receipt import (
        empty_test_counts,
        merge_test_counts,
        summarize_junit_xml,
        write_proof_receipt,
    )
except ModuleNotFoundError:  # pragma: no cover - exercised via module import tests
    from scripts.proof_receipt import (
        empty_test_counts,
        merge_test_counts,
        summarize_junit_xml,
        write_proof_receipt,
    )

DEFAULT_MEMORY_SERVICE_PORT = (
    os.environ.get("MEMORY_SERVICE_PORT", "").strip() or "3031"
)

MEMORY_SERVICE_URL = os.environ.get(
    "MEMORY_SERVICE_URL",
    f"http://localhost:{DEFAULT_MEMORY_SERVICE_PORT}",
)
LIVE_MONGO_URL = os.environ.get(
    "MONGO_URL",
    "mongodb://127.0.0.1:27017",
)
LIVE_MONGO_DB_NAME = os.environ.get(
    "DB_NAME",
    "hysight_live",
)

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
EXPECTED_HCA_PACKAGE_DIR = (REPO_ROOT / "hca" / "src" / "hca").resolve()
PACKAGE_AUTHORITY_SENTENCE = (
    "The Python runtime package lives under ./hca and is installed editable as part of repo bootstrap."
)
BOOTSTRAP_GUIDE = "BOOTSTRAP.md"
BOOTSTRAP_HINT = f"See {BOOTSTRAP_GUIDE} for the supported bootstrap path."
REPO_VENV_DIR = (REPO_ROOT / ".venv").resolve()
PROOF_ARTIFACT_DIR = REPO_ROOT / "artifacts" / "proof"
PROOF_HISTORY_DIR = PROOF_ARTIFACT_DIR / "history"
JUNIT_DIR = REPO_ROOT / "test_reports" / "pytest"
OPTIONAL_PROOF_STALENESS_DAYS = int(
    os.environ.get("HYSIGHT_OPTIONAL_PROOF_STALENESS_DAYS", "30")
)
PROOF_ENVIRONMENT_MODE_ENV = "HYSIGHT_PROOF_ENVIRONMENT_MODE"
PROOF_SERVICE_CONNECTION_MODE_ENV = "HYSIGHT_PROOF_SERVICE_CONNECTION_MODE"

COLLECTION_ISSUE_PATTERNS = {
    "pytest_collection_warning": re.compile(r"PytestCollectionWarning"),
    "pytest_unknown_mark_warning": re.compile(r"PytestUnknownMarkWarning"),
    "collection_error": re.compile(r"ERROR collecting "),
    "zero_items_collected": re.compile(r"collected 0 items"),
}

# ---------------------------------------------------------------------------
# Proof surface definition
# ---------------------------------------------------------------------------

Step = Dict[str, Any]
StepResult = Dict[str, Any]

STEP_JUNIT_FILENAMES = {
    "pipeline": "hca-pipeline-proof.xml",
    "backend-baseline": "backend-baseline-proof.xml",
    "contract": "contract-conformance-proof.xml",
    "integration": "backend-integration-proof.xml",
    "mongo-live": "backend-live-mongo-proof.xml",
    "sidecar": "backend-live-sidecar-proof.xml",
    "autonomy-optional": "backend-autonomy-optional-proof.xml",
}

FRONTEND_PROOF_RECEIPT_PATH = PROOF_ARTIFACT_DIR / "frontend.json"

EXPECTED_BASELINE_STEP_COUNTS = {
    "pipeline": {
        "total_test_count": 7,
        "passed_test_count": 7,
        "skipped_test_count": 0,
        "failed_test_count": 0,
        "error_test_count": 0,
    },
    "backend-baseline": {
        "total_test_count": 98,
        "passed_test_count": 98,
        "skipped_test_count": 0,
        "failed_test_count": 0,
        "error_test_count": 0,
    },
    "contract": {
        "total_test_count": 18,
        "passed_test_count": 18,
        "skipped_test_count": 0,
        "failed_test_count": 0,
        "error_test_count": 0,
    },
}


BASELINE_STEPS: List[Step] = [
    {
        "id": "pipeline",
        "name": "HCA pipeline proof",
        "receipt_name": "pipeline",
        "isolated_storage": True,
        "cmd": [
            sys.executable, "-m", "pytest",
            "tests/test_hca_pipeline.py", "-q",
        ],
    },
    {
        "id": "backend-baseline",
        "name": "Backend baseline proof",
        "receipt_name": "backend-baseline",
        "isolated_storage": True,
        "cmd": [
            sys.executable, "-m", "pytest",
            "backend/tests/test_hca.py",
            "backend/tests/test_memory.py",
            "backend/tests/test_server_bootstrap.py",
            "-q",
        ],
    },
    {
        "id": "contract",
        "name": "Contract conformance proof",
        "receipt_name": "contract",
        "isolated_storage": True,
        "cmd": [
            sys.executable, "-m", "pytest",
            "backend/tests/test_contract_conformance.py", "-q",
        ],
    },
]

INTEGRATION_STEP: Step = {
    "id": "integration",
    "name": "Backend integration proof",
    "receipt_name": "integration",
    "isolated_storage": True,
    "cmd": [
        sys.executable, "-m", "pytest",
        "backend/tests/test_memvid_sidecar.py",
        "-q",
        "--run-integration",
    ],
}

MONGO_LIVE_STEP: Step = {
    "id": "mongo-live",
    "name": "Backend live Mongo proof",
    "receipt_name": "live-mongo",
    "isolated_storage": True,
    "cmd": [
        sys.executable, "-m", "pytest",
        "backend/tests/test_status_live_mongo.py",
        "-q",
        "--run-live",
    ],
    "env": {
        "RUN_MONGO_TESTS": "1",
        "MONGO_URL": LIVE_MONGO_URL,
        "DB_NAME": LIVE_MONGO_DB_NAME,
    },
}

SIDECAR_STEP: Step = {
    "id": "sidecar",
    "name": "Backend live sidecar proof",
    "receipt_name": "live-sidecar",
    "isolated_storage": True,
    "cmd": [
        sys.executable, "-m", "pytest",
        "backend/tests/test_memvid_sidecar.py",
        "-q",
        "--run-live",
    ],
    "env": {
        "RUN_MEMVID_TESTS": "1",
        "MEMORY_BACKEND": "rust",
        "MEMORY_SERVICE_URL": MEMORY_SERVICE_URL,
    },
}

FRONTEND_STEP: Step = {
    "id": "frontend",
    "name": "Frontend proof",
    "receipt_name": "frontend",
    "external_receipt": FRONTEND_PROOF_RECEIPT_PATH,
    "cmd": [sys.executable, "scripts/proof_frontend.py"],
}

AUTONOMY_OPTIONAL_STEP: Step = {
    "id": "autonomy-optional",
    "name": "Bounded autonomy proof (optional)",
    "receipt_name": "autonomy-optional",
    "isolated_storage": True,
    "cmd": [
        sys.executable, "-m", "pytest",
        "backend/tests/test_autonomy_policy.py",
        "backend/tests/test_autonomy_supervisor.py",
        "backend/tests/test_autonomy_routes.py",
        "backend/tests/test_autonomy_resume.py",
        "backend/tests/test_autonomy_budgets.py",
        "backend/tests/test_autonomy_events.py",
        "backend/tests/test_autonomy_kill_switch.py",
        "backend/tests/test_autonomy_dedupe.py",
        "backend/tests/test_autonomy_lifecycle.py",
        "backend/tests/test_autonomy_style_profile.py",
        "backend/tests/test_autonomy_attention_controller.py",
        "backend/tests/test_autonomy_reanchor.py",
        "-q",
    ],
}

ALL_PROOF_STEP_IDS = (
    "pipeline",
    "backend-baseline",
    "contract",
    "frontend",
    "integration",
    "mongo-live",
    "sidecar",
    "autonomy-optional",
)

OPTIONAL_PROOF_STEP_IDS = (
    "frontend",
    "integration",
    "mongo-live",
    "sidecar",
    "autonomy-optional",
)

# ---------------------------------------------------------------------------
# Dependency / environment checks
# ---------------------------------------------------------------------------

BASELINE_REQUIRED_TEST_DEPS = {
    "pytest": "pytest",
    "requests": "requests",
    "requests_mock": "requests-mock",
    "httpx": "httpx",
    "jsonschema": "jsonschema",
}

MONGO_REQUIRED_DEPS = {
    "motor": "motor",
    "pymongo": "pymongo",
}

OPTIONAL_PROOF_ENV_KEYS = (
    "RUN_MEMVID_TESTS",
    "MEMORY_SERVICE_URL",
    "RUN_MONGO_TESTS",
    "MONGO_URL",
    "DB_NAME",
)

BASELINE_TEST_HINT = "make venv"
MONGO_TEST_HINT = (
    "make venv && ./.venv/bin/python -m pip install -r backend/requirements-integration.txt"
)


def _repair_command(include_integration: bool) -> str:
    if include_integration:
        return (
            "make venv && ./.venv/bin/python -m pip install "
            "-r backend/requirements-integration.txt"
        )
    return "make venv"


def _strict_venv_requested(args: argparse.Namespace) -> bool:
    return any(
        (
            bool(args.strict_venv),
            os.environ.get("HYSIGHT_STRICT_VENV") == "1",
            os.environ.get("CI", "").lower() == "true",
            os.environ.get("GITHUB_ACTIONS", "").lower() == "true",
        )
    )


def _validate_repo_local_venv(*, strict: bool) -> bool:
    current_prefix = pathlib.Path(sys.prefix).resolve()
    if current_prefix == REPO_VENV_DIR:
        return True

    message = (
        "Hysight proofs are expected to run from the repo-local .venv.\n"
        f"Resolved sys.prefix: {current_prefix}\n"
        f"Expected .venv: {REPO_VENV_DIR}\n"
        f"Repair:\n    { _repair_command(include_integration=False) }\n"
        f"{BOOTSTRAP_HINT}"
    )
    if strict:
        print(message, file=sys.stderr)
        return False

    print(f"WARNING: {message}", file=sys.stderr)
    return True


def _validate_hca_package_authority(*, include_integration: bool) -> bool:
    spec = importlib.util.find_spec("hca")
    resolved_origin = None
    if spec is not None and spec.origin is not None:
        resolved_origin = pathlib.Path(spec.origin).resolve()

    if resolved_origin is not None and resolved_origin.parent == EXPECTED_HCA_PACKAGE_DIR:
        return True

    print(PACKAGE_AUTHORITY_SENTENCE)
    print(
        "Resolved hca from: "
        f"{resolved_origin or 'not installed or ambiguous namespace package'}"
    )
    print(f"Expected editable source under: {EXPECTED_HCA_PACKAGE_DIR}")
    print("Repair:\n    " + _repair_command(include_integration))
    print(BOOTSTRAP_HINT)
    return False


def _isolated_proof_env(storage_root: pathlib.Path) -> Dict[str, str]:
    return {
        "MEMORY_BACKEND": "python",
        "HCA_STORAGE_ROOT": str(storage_root),
        "MEMORY_STORAGE_DIR": str(storage_root / "memory"),
    }


def _missing_dependencies(requirements: Dict[str, str]) -> List[str]:
    missing = []
    for module_name, package_name in requirements.items():
        if importlib.util.find_spec(module_name) is None:
            missing.append(package_name)
    return missing


def _print_missing_dependencies(missing: List[str], install_hint: str) -> None:
    joined = ", ".join(sorted(missing))
    print(
        "Missing required Python dependencies: "
        f"{joined}.\nRun:\n    {install_hint}\n{BOOTSTRAP_HINT}"
    )


def _check_mongo_health() -> bool:
    client = None
    try:
        pymongo = importlib.import_module("pymongo")
        client = pymongo.MongoClient(
            LIVE_MONGO_URL,
            serverSelectionTimeoutMS=1000,
        )
        client.admin.command("ping")
        return True
    except Exception:
        return False
    finally:
        try:
            client.close()
        except Exception:
            pass


def _check_sidecar_health() -> bool:
    """Return True if the memvid sidecar health endpoint is reachable."""
    try:
        import urllib.error
        import urllib.parse
        import urllib.request

        parsed = urllib.parse.urlparse(MEMORY_SERVICE_URL)
        if parsed.scheme != "http":
            return False
        if parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
            # Only probe loopback addresses to avoid SSRF via env-var
            # injection.
            return False

        health_url = urllib.parse.urlunparse(
            (
                parsed.scheme,
                parsed.netloc,
                "/health",
                "",
                "",
                "",
            )
        )
        urllib.request.urlopen(health_url, timeout=3)
        return True
    except (ValueError, urllib.error.URLError, OSError):
        return False


def _step_junit_path(step_id: str) -> pathlib.Path:
    JUNIT_DIR.mkdir(parents=True, exist_ok=True)
    return JUNIT_DIR / STEP_JUNIT_FILENAMES[step_id]


def _build_pytest_command(step: Step, junit_xml: pathlib.Path) -> List[str]:
    return [
        *step["cmd"],
        "-ra",
        "--strict-markers",
        f"--junitxml={junit_xml}",
    ]


def _collection_issues(output: str) -> List[str]:
    issues = []
    for label, pattern in COLLECTION_ISSUE_PATTERNS.items():
        if pattern.search(output):
            issues.append(label)
    return issues


def _read_receipt_timestamp(receipt_path: pathlib.Path) -> datetime | None:
    if not receipt_path.exists():
        return None
    try:
        payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    raw_timestamp = payload.get("timestamp") or payload.get("generated_at")
    if not raw_timestamp:
        return None
    try:
        return datetime.fromisoformat(raw_timestamp.replace("Z", "+00:00"))
    except ValueError:
        return None


def _warn_if_stale_optional_receipt(
    *,
    proof_name: str,
    receipt_path: pathlib.Path,
    threshold_days: int,
) -> None:
    previous_timestamp = _read_receipt_timestamp(receipt_path)
    if previous_timestamp is None:
        return
    age = datetime.now(timezone.utc) - previous_timestamp.astimezone(timezone.utc)
    if age.days < threshold_days:
        return
    print(
        "WARNING: last "
        f"{proof_name} receipt is {age.days} day(s) old "
        f"({previous_timestamp.isoformat()}). Optional proof may be stale.",
        file=sys.stderr,
    )


def _summarize_proof_receipt(
    receipt_path: pathlib.Path,
) -> tuple[
    Dict[str, int],
    List[Dict[str, str]],
    Dict[str, Any] | None,
    str | None,
    str | None,
    str | None,
]:
    counts = empty_test_counts()
    if not receipt_path.exists():
        return counts, [], None, f"missing proof receipt: {receipt_path}", None, None

    try:
        payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return counts, [], None, f"invalid proof receipt json: {exc}", None, None

    for key in counts:
        try:
            counts[key] = int(payload.get(key, 0))
        except (TypeError, ValueError):
            return counts, [], None, f"invalid count field {key!r} in proof receipt", None, None

    skipped_cases = payload.get("skipped_cases")
    if not isinstance(skipped_cases, list):
        skipped_cases = []

    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        metadata = None

    receipt_error = payload.get("junit_summary_error")
    if receipt_error is not None and not isinstance(receipt_error, str):
        receipt_error = "invalid receipt error field"

    outcome = payload.get("outcome")
    if outcome is not None and not isinstance(outcome, str):
        outcome = None

    failure_reason = payload.get("failure_reason")
    if failure_reason is not None and not isinstance(failure_reason, str):
        failure_reason = None

    return counts, skipped_cases, metadata, receipt_error, outcome, failure_reason


def _invocation_receipt_name(
    args: argparse.Namespace,
    steps: Sequence[Step],
) -> str:
    if args.baseline_step:
        return args.baseline_step
    if not any(
        (args.frontend, args.integration, args.mongo_live, args.sidecar, args.autonomy)
    ):
        return "baseline"
    if len(steps) == 1:
        return str(steps[0]["receipt_name"])
    joined = "-".join(step["receipt_name"] for step in steps)
    return f"composite-{joined}"


def _receipt_path_for_name(name: str) -> pathlib.Path:
    PROOF_ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    return PROOF_ARTIFACT_DIR / f"{name}.json"


def _history_receipt_path(name: str) -> pathlib.Path:
    PROOF_HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return PROOF_HISTORY_DIR / f"{name}-{timestamp}.json"


def _environment_mode() -> str:
    if os.environ.get(PROOF_ENVIRONMENT_MODE_ENV):
        return os.environ[PROOF_ENVIRONMENT_MODE_ENV]
    if pathlib.Path(sys.prefix).resolve() == REPO_VENV_DIR:
        return "repo_local_venv"
    return "external_python"


def _service_connection_mode(name: str) -> str:
    if os.environ.get(PROOF_SERVICE_CONNECTION_MODE_ENV):
        return os.environ[PROOF_SERVICE_CONNECTION_MODE_ENV]
    if name == "live-mongo":
        return "manual:existing-mongo"
    if name == "live-sidecar":
        return "manual:existing-sidecar"
    if name == "integration":
        return "mocked-boundary"
    return "none"


def _service_endpoint(name: str) -> str:
    if name == "live-mongo":
        return LIVE_MONGO_URL
    if name == "live-sidecar":
        return MEMORY_SERVICE_URL
    return "n/a"


def _receipt_scope_metadata(
    steps: Sequence[Step],
    results: Sequence[StepResult],
) -> Dict[str, Any]:
    covered_step_ids = [str(step["id"]) for step in steps]
    omitted_step_ids = [
        step_id for step_id in ALL_PROOF_STEP_IDS if step_id not in covered_step_ids
    ]
    passed_step_ids = []
    failed_step_ids = []

    for result in results:
        proof_outcome = result.get("proof_outcome")
        passed = result.get("returncode") == 0 and proof_outcome in {
            None,
            "passed",
        }
        if passed:
            passed_step_ids.append(str(result["id"]))
        else:
            failed_step_ids.append(str(result["id"]))

    return {
        "receipt_scope": (
            "This receipt covers only the proof steps listed in "
            "covered_proof_steps."
        ),
        "covered_proof_steps": covered_step_ids,
        "omitted_proof_steps": omitted_step_ids,
        "passed_proof_steps": passed_step_ids,
        "failed_proof_steps": failed_step_ids,
        "includes_optional_proof_steps": any(
            step_id in OPTIONAL_PROOF_STEP_IDS for step_id in covered_step_ids
        ),
    }


def _counts_delta_message(
    *,
    step_name: str,
    key: str,
    expected: int,
    actual: int,
) -> str:
    delta = actual - expected
    return (
        f"{step_name}: expected {key}={expected}, got {actual} "
        f"(delta {delta:+d})."
    )


def _validate_baseline_result(result: StepResult) -> List[str]:
    errors = []
    expected = EXPECTED_BASELINE_STEP_COUNTS[result["id"]]
    for key, expected_value in expected.items():
        actual = int(result["counts"].get(key, 0))
        if actual != expected_value:
            errors.append(
                _counts_delta_message(
                    step_name=result["name"],
                    key=key,
                    expected=expected_value,
                    actual=actual,
                )
            )
    if result["counts"]["skipped_test_count"] > 0:
        skipped_cases = result["skipped_cases"] or []
        skipped_summary = "; ".join(
            f"{case['classname']}::{case['name']} ({case['message']})"
            for case in skipped_cases
        )
        errors.append(
            "Baseline proof does not allow unexpected skips. "
            f"Skipped cases: {skipped_summary or 'unknown skip reason'}"
        )
    return errors


def _validate_result(step: Step, result: StepResult) -> List[str]:
    errors = []
    if result["junit_error"]:
        errors.append(
            f"{step['name']}: unable to parse JUnit XML: {result['junit_error']}"
        )
    if result["collection_issues"]:
        errors.append(
            f"{step['name']}: pytest reported collection issues: "
            f"{', '.join(result['collection_issues'])}"
        )
    if step.get("external_receipt") and result.get("proof_outcome") not in {None, "passed"}:
        errors.append(
            f"{step['name']}: external proof receipt outcome was "
            f"{result.get('proof_outcome')!r}"
        )
    if step["id"] in EXPECTED_BASELINE_STEP_COUNTS:
        errors.extend(_validate_baseline_result(result))
    return errors


def _write_invocation_receipt(
    *,
    receipt_name: str,
    steps: Sequence[Step],
    results: Sequence[StepResult],
    outcome: str,
    failure_reason: str | None,
) -> None:
    metadata = {
        **_receipt_scope_metadata(steps, results),
        "steps": [
            {
                "id": result["id"],
                "name": result["name"],
                "returncode": result["returncode"],
                "outcome": result.get("proof_outcome")
                or ("passed" if result["returncode"] == 0 else "failed"),
                "counts": result["counts"],
                "junit_xml": (
                    str(result["junit_xml"].relative_to(REPO_ROOT))
                    if isinstance(result.get("junit_xml"), pathlib.Path)
                    and result["junit_xml"].exists()
                    else None
                ),
                "receipt_json": (
                    str(result["receipt_path"].relative_to(REPO_ROOT))
                    if isinstance(result.get("receipt_path"), pathlib.Path)
                    and result["receipt_path"].exists()
                    else None
                ),
                "collection_issues": result["collection_issues"],
                "skipped_cases": result["skipped_cases"],
                "proof_metadata": result.get("proof_metadata"),
                "proof_failure_reason": result.get("proof_failure_reason"),
            }
            for result in results
        ],
    }
    latest_receipt_path = _receipt_path_for_name(receipt_name)
    aggregate_counts = merge_test_counts(*(result["counts"] for result in results))
    write_proof_receipt(
        output_path=latest_receipt_path,
        proof_tier=receipt_name,
        environment_mode=_environment_mode(),
        service_connection_mode=_service_connection_mode(receipt_name),
        service_endpoint=_service_endpoint(receipt_name),
        command=shlex.join([sys.executable, *sys.argv]),
        counts=aggregate_counts,
        outcome=outcome,
        failure_reason=failure_reason,
        metadata=metadata,
    )
    if receipt_name in {"live-mongo", "live-sidecar"}:
        history_receipt_path = _history_receipt_path(receipt_name)
        write_proof_receipt(
            output_path=history_receipt_path,
            proof_tier=receipt_name,
            environment_mode=_environment_mode(),
            service_connection_mode=_service_connection_mode(receipt_name),
            service_endpoint=_service_endpoint(receipt_name),
            command=shlex.join([sys.executable, *sys.argv]),
            counts=aggregate_counts,
            outcome=outcome,
            failure_reason=failure_reason,
            metadata=metadata,
        )


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def _run_external_receipt_step(step: Step) -> StepResult:
    receipt_path = pathlib.Path(step["external_receipt"])
    receipt_path.unlink(missing_ok=True)
    cmd = list(step["cmd"])
    extra_env = step.get("env", {})
    env = dict(os.environ)
    env.update(extra_env)

    print(f"\n==> [{step['name']}]")
    display_env = " ".join(f"{k}={v}" for k, v in extra_env.items())
    display_cmd = shlex.join(cmd)
    if display_env:
        print(f"    {display_env} {display_cmd}")
    else:
        print(f"    {display_cmd}")

    completed = subprocess.run(
        cmd,
        env=env,
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.stdout:
        print(completed.stdout, end="")
    if completed.stderr:
        print(completed.stderr, end="", file=sys.stderr)

    counts, skipped_cases, proof_metadata, receipt_error, proof_outcome, proof_failure_reason = _summarize_proof_receipt(
        receipt_path
    )
    return {
        "id": step["id"],
        "name": step["name"],
        "receipt_name": step["receipt_name"],
        "returncode": completed.returncode,
        "junit_xml": None,
        "receipt_path": receipt_path,
        "counts": counts,
        "skipped_cases": skipped_cases,
        "junit_error": receipt_error,
        "collection_issues": [],
        "proof_metadata": proof_metadata,
        "proof_outcome": proof_outcome,
        "proof_failure_reason": proof_failure_reason,
    }

def _run_step(step: Step) -> StepResult:
    if step.get("external_receipt"):
        return _run_external_receipt_step(step)

    junit_xml = _step_junit_path(step["id"])
    junit_xml.unlink(missing_ok=True)
    cmd = _build_pytest_command(step, junit_xml)
    extra_env = step.get("env", {})
    isolated_dir = None
    isolated_env: Dict[str, str] = {}
    if step.get("isolated_storage"):
        isolated_dir = pathlib.Path(
            tempfile.mkdtemp(prefix="hysight-proof-")
        ).resolve()
        isolated_env = _isolated_proof_env(isolated_dir)

    env = dict(os.environ)
    for key in OPTIONAL_PROOF_ENV_KEYS:
        if key not in extra_env:
            env.pop(key, None)
    env.update(isolated_env)
    env.update(extra_env)

    print(f"\n==> [{step['name']}]")
    display_env_map = {**isolated_env, **extra_env}
    display_env = " ".join(
        f"{k}={v}" for k, v in display_env_map.items()
    )
    display_cmd = shlex.join(cmd)
    if display_env:
        print(f"    {display_env} {display_cmd}")
    else:
        print(f"    {display_cmd}")

    try:
        completed = subprocess.run(
            cmd,
            env=env,
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.stdout:
            print(completed.stdout, end="")
        if completed.stderr:
            print(completed.stderr, end="", file=sys.stderr)

        counts, skipped_cases, junit_error = summarize_junit_xml(
            junit_xml if junit_xml.exists() else None
        )
        output = f"{completed.stdout}\n{completed.stderr}".strip()
        return {
            "id": step["id"],
            "name": step["name"],
            "receipt_name": step["receipt_name"],
            "returncode": completed.returncode,
            "junit_xml": junit_xml,
            "counts": counts,
            "skipped_cases": skipped_cases,
            "junit_error": junit_error,
            "collection_issues": _collection_issues(output),
        }
    finally:
        if isolated_dir is not None:
            for path in sorted(isolated_dir.rglob("*"), reverse=True):
                if path.is_file() or path.is_symlink():
                    path.unlink(missing_ok=True)
                elif path.is_dir():
                    path.rmdir()
            isolated_dir.rmdir()


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--baseline-step",
        choices=("pipeline", "backend-baseline", "contract"),
        help=(
            "Run a single baseline proof step through the canonical runner. "
            "Used by Make targets and CI jobs that want per-surface receipts."
        ),
    )
    parser.add_argument(
        "--frontend",
        action="store_true",
        help=(
            "Run the opt-in frontend proof tier. Requires Node 24.x, "
            "Yarn 1.22.22, installed frontend dependencies, and the repo-local "
            "Python test environment."
        ),
    )
    parser.add_argument(
        "--integration",
        action="store_true",
        help=(
            "Run the opt-in backend integration proof tier. This exercises "
            "the mock-backed memvid boundary tests without requiring a live sidecar."
        ),
    )
    parser.add_argument(
        "--mongo-live",
        action="store_true",
        help=(
            "Run the opt-in live Mongo proof. Requires reachable Mongo at "
            f"{LIVE_MONGO_URL} and optional extras from "
            "backend/requirements-integration.txt."
        ),
    )
    parser.add_argument(
        "--sidecar",
        action="store_true",
        help=(
            "Run the opt-in live sidecar proof. Requires a running memvid "
            f"sidecar at {MEMORY_SERVICE_URL}. Override the default loopback "
            "port with MEMORY_SERVICE_PORT or set a full MEMORY_SERVICE_URL "
            "explicitly."
        ),
    )
    parser.add_argument(
        "--autonomy",
        action="store_true",
        help=(
            "Run the opt-in bounded autonomy proof. Exercises the autonomy "
            "policy, supervisor, routes, resume safety, budgets, and event "
            "log integration tests. Not part of the baseline contract."
        ),
    )
    parser.add_argument(
        "--strict-venv",
        action="store_true",
        help=(
            "Fail instead of warn when sys.prefix does not resolve to the "
            "repo-local .venv. CI also enables this behavior automatically."
        ),
    )
    args = parser.parse_args()

    if args.baseline_step and any(
        (args.frontend, args.integration, args.mongo_live, args.sidecar, args.autonomy)
    ):
        print(
            "--baseline-step cannot be combined with optional proof flags.",
            file=sys.stderr,
        )
        return 1

    if not _validate_repo_local_venv(strict=_strict_venv_requested(args)):
        return 1

    if not _validate_hca_package_authority(
        include_integration=bool(args.frontend or args.integration or args.mongo_live)
    ):
        return 1

    baseline_missing = _missing_dependencies(BASELINE_REQUIRED_TEST_DEPS)
    if baseline_missing:
        _print_missing_dependencies(baseline_missing, BASELINE_TEST_HINT)
        return 1

    if args.mongo_live:
        mongo_missing = _missing_dependencies(MONGO_REQUIRED_DEPS)
        if mongo_missing:
            _print_missing_dependencies(mongo_missing, MONGO_TEST_HINT)
            return 1
        if not _check_mongo_health():
            print(
                "Mongo live proof requested, but the configured MongoDB "
                f"instance is not reachable at {LIVE_MONGO_URL}.\n"
                "Set MONGO_URL and DB_NAME for the target instance or start "
                "a local MongoDB server before re-running."
            )
            return 1

    if args.sidecar and not _check_sidecar_health():
        print(
            f"Sidecar mode requested, but health check failed at "
            f"{MEMORY_SERVICE_URL}/health\n"
            "Start the memvid sidecar first:\n"
            "    cargo run --manifest-path memvid_service/Cargo.toml --release\n"
            f"{BOOTSTRAP_HINT}"
        )
        return 1

    if args.baseline_step:
        steps = [
            next(step for step in BASELINE_STEPS if step["id"] == args.baseline_step)
        ]
    elif not any(
        (args.frontend, args.integration, args.mongo_live, args.sidecar, args.autonomy)
    ):
        steps = list(BASELINE_STEPS)
    else:
        steps = []
        if args.frontend:
            steps.append(FRONTEND_STEP)
        if args.integration:
            steps.append(INTEGRATION_STEP)
        if args.mongo_live:
            steps.append(MONGO_LIVE_STEP)
        if args.sidecar:
            steps.append(SIDECAR_STEP)
        if args.autonomy:
            steps.append(AUTONOMY_OPTIONAL_STEP)

    receipt_name = _invocation_receipt_name(args, steps)
    latest_receipt_path = _receipt_path_for_name(receipt_name)
    if receipt_name in {"live-mongo", "live-sidecar"}:
        _warn_if_stale_optional_receipt(
            proof_name=receipt_name,
            receipt_path=latest_receipt_path,
            threshold_days=OPTIONAL_PROOF_STALENESS_DAYS,
        )

    print(f"Running {len(steps)} proof step(s).")
    results: List[StepResult] = []
    outcome = "failed"
    failure_reason = None
    exit_code = 1
    try:
        for step in steps:
            result = _run_step(step)
            results.append(result)
            if result["returncode"] != 0:
                failure_reason = result.get("proof_failure_reason") or (
                    f"[{step['name']}] exited with code {result['returncode']}"
                )
                print(f"\nFAILED: {failure_reason}")
                return result["returncode"]

        validation_errors: List[str] = []
        for step, result in zip(steps, results):
            validation_errors.extend(_validate_result(step, result))

        if validation_errors:
            failure_reason = "\n".join(validation_errors)
            print("\nFAILED: proof invariants did not hold.", file=sys.stderr)
            for error in validation_errors:
                print(f" - {error}", file=sys.stderr)
            return 1

        outcome = "passed"
        exit_code = 0
        aggregate_counts = merge_test_counts(*(result["counts"] for result in results))
        print(
            "\nAll "
            f"{len(steps)} proof step(s) passed "
            f"({aggregate_counts['passed_test_count']} passed, "
            f"{aggregate_counts['skipped_test_count']} skipped)."
        )
        return 0
    finally:
        if steps:
            _write_invocation_receipt(
                receipt_name=receipt_name,
                steps=steps,
                results=results,
                outcome=outcome,
                failure_reason=failure_reason,
            )


if __name__ == "__main__":
    sys.exit(main())
