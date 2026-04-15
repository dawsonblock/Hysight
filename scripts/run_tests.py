#!/usr/bin/env python3
"""Universal test runner for Hysight.

Default mode runs only the supported service-free local baseline proof surface:

    python scripts/run_tests.py

Optional proof tiers are explicit and do not broaden the baseline contract:

    python scripts/run_tests.py --integration

    MONGO_URL=mongodb://127.0.0.1:27017 \
    DB_NAME=hysight_live \
    python scripts/run_tests.py --mongo-live

    MEMORY_SERVICE_PORT=3032 \
    python scripts/run_tests.py --sidecar

Proof modes and their corresponding CI job names:
- Baseline local proof    → CI: Baseline Local Proof Surface
- HCA pipeline proof      → CI: HCA Smoke Proof
- Contract conformance    → CI: Contract Conformance Proof
- Backend baseline proof  → CI: Backend Baseline Proof
- Backend integration     → CI: Backend Integration Proof   (--integration)
- Live Mongo proof        → CI: Backend Live Mongo Proof    (--mongo-live)
- Live sidecar proof      → CI: Backend Live Sidecar Proof  (--sidecar)
"""

import argparse
import importlib
import importlib.util
import os
import pathlib
import shlex
import subprocess
import sys
import tempfile
from typing import Any, Dict, List

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

# Repo root is two levels up from this file (scripts/run_tests.py → repo root).
REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
EXPECTED_HCA_PACKAGE_DIR = (REPO_ROOT / "hca" / "src" / "hca").resolve()
PACKAGE_AUTHORITY_SENTENCE = (
    "The Python runtime package lives under ./hca and is installed editable as part of repo bootstrap."
)

# ---------------------------------------------------------------------------
# Proof surface definition
# ---------------------------------------------------------------------------

Step = Dict[str, Any]


BASELINE_STEPS: List[Step] = [
    {
        "name": "HCA pipeline proof",
        "isolated_storage": True,
        "cmd": [
            sys.executable, "-m", "pytest",
            "tests/test_hca_pipeline.py", "-q",
        ],
    },
    {
        "name": "Backend baseline proof",
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
        "name": "Contract conformance proof",
        "isolated_storage": True,
        "cmd": [
            sys.executable, "-m", "pytest",
            "backend/tests/test_contract_conformance.py", "-q",
        ],
    },
]

INTEGRATION_STEP: Step = {
    "name": "Backend integration proof",
    "isolated_storage": True,
    "cmd": [
        sys.executable, "-m", "pytest",
        "backend/tests/test_memvid_sidecar.py",
        "-q",
        "--run-integration",
    ],
}

MONGO_LIVE_STEP: Step = {
    "name": "Backend live Mongo proof",
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
    "name": "Backend live sidecar proof",
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

BASELINE_TEST_HINT = (
    "python -m pip install -r backend/requirements-test.txt"
)
MONGO_TEST_HINT = (
    "python -m pip install -r backend/requirements-integration.txt"
)


def _repair_command(include_integration: bool) -> str:
    bootstrap_target = (
        "make test-bootstrap-integration"
        if include_integration
        else "make test-bootstrap"
    )
    return "\n    ".join(
        [
            "make venv",
            "source .venv/bin/activate",
            bootstrap_target,
        ]
    )


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
        f"{joined}.\nRun:\n    {install_hint}"
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


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def _run_step(step: Step) -> int:
    cmd = step["cmd"]
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
        result = subprocess.run(cmd, env=env, cwd=REPO_ROOT, check=False)
        return result.returncode
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
    args = parser.parse_args()

    if not _validate_hca_package_authority(
        include_integration=bool(args.integration or args.mongo_live)
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
            "    cargo run --manifest-path memvid_service/Cargo.toml --release"
        )
        return 1

    if not any((args.integration, args.mongo_live, args.sidecar)):
        steps = list(BASELINE_STEPS)
    else:
        steps = []
        if args.integration:
            steps.append(INTEGRATION_STEP)
        if args.mongo_live:
            steps.append(MONGO_LIVE_STEP)
        if args.sidecar:
            steps.append(SIDECAR_STEP)

    print(f"Running {len(steps)} proof step(s).")
    for step in steps:
        rc = _run_step(step)
        if rc != 0:
            print(f"\nFAILED: [{step['name']}] exited with code {rc}")
            return rc

    print(f"\nAll {len(steps)} proof step(s) passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
