#!/usr/bin/env python3
"""Universal test runner for Hysight.

Default mode runs the full supported proof surface without any external
services:

    python scripts/run_tests.py

Optional live sidecar proof (requires a running memvid sidecar):

    RUN_MEMVID_TESTS=1 python scripts/run_tests.py --sidecar

Proof modes and their corresponding CI job names:
- HCA pipeline proof      → CI: HCA Smoke Proof
- Contract conformance    → CI: Contract Conformance Proof
- Backend local proof     → CI: Backend Local Proof
- Backend full proof      → CI: Backend Full Proof
- Live sidecar proof      → CI: Backend Live Sidecar Proof  (--sidecar only)
"""

import argparse
import importlib.util
import os
import pathlib
import shlex
import subprocess
import sys

MEMORY_SERVICE_URL = os.environ.get("MEMORY_SERVICE_URL", "http://localhost:3031")

# Repo root is two levels up from this file (scripts/run_tests.py → repo root).
REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Proof surface definition
# ---------------------------------------------------------------------------

DEFAULT_STEPS = [
    {
        "name": "HCA pipeline proof",
        "cmd": [
            sys.executable, "-m", "pytest",
            "tests/test_hca_pipeline.py", "-q",
        ],
    },
    {
        "name": "Backend local proof",
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
        "cmd": [
            sys.executable, "-m", "pytest",
            "backend/tests/test_contract_conformance.py", "-q",
        ],
    },
    {
        "name": "Backend full proof",
        "cmd": [
            sys.executable, "-m", "pytest",
            "backend/tests", "-q",
        ],
    },
]

SIDECAR_STEP = {
    "name": "Live sidecar proof",
    "cmd": [
        sys.executable, "-m", "pytest",
        "backend/tests/test_memvid_sidecar.py", "-q",
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

REQUIRED_TEST_DEPS = (
    "pytest",
    "requests_mock",
    "httpx",
    "jsonschema",
)


def _check_test_deps() -> bool:
    """Return True if all required test dependencies are importable."""
    for pkg in REQUIRED_TEST_DEPS:
        if importlib.util.find_spec(pkg) is None:
            return False
    return True


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
            # Only probe loopback addresses to avoid SSRF via env-var injection.
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

def _run_step(step: dict) -> int:
    cmd = step["cmd"]
    extra_env = step.get("env", {})
    env = {**os.environ, **extra_env}

    print(f"\n==> [{step['name']}]")
    display_env = " ".join(f"{k}={v}" for k, v in extra_env.items())
    display_cmd = shlex.join(cmd)
    if display_env:
        print(f"    {display_env} {display_cmd}")
    else:
        print(f"    {display_cmd}")

    result = subprocess.run(cmd, env=env, cwd=REPO_ROOT, check=False)
    return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--sidecar",
        action="store_true",
        help=(
            "Also run the live sidecar proof. "
            f"Requires a running memvid sidecar at {MEMORY_SERVICE_URL} "
            "and RUN_MEMVID_TESTS=1 in the environment."
        ),
    )
    args = parser.parse_args()

    # -- dependency check before we touch any test commands --
    if not _check_test_deps():
        print(
            "Missing test dependencies. Run:\n"
            "    python -m pip install -r backend/requirements-test.txt"
        )
        return 1

    # -- sidecar pre-flight when requested --
    if args.sidecar:
        if not os.environ.get("RUN_MEMVID_TESTS"):
            print(
                "Sidecar mode requested but RUN_MEMVID_TESTS is not set.\n"
                "Re-run with:\n"
                f"    RUN_MEMVID_TESTS=1 python scripts/run_tests.py --sidecar"
            )
            return 1
        if not _check_sidecar_health():
            print(
                f"Sidecar mode requested, but health check failed at "
                f"{MEMORY_SERVICE_URL}/health\n"
                "Start the memvid sidecar first:\n"
                "    ./memvid_service/target/release/memvid-sidecar"
            )
            return 1

    steps = list(DEFAULT_STEPS)
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
