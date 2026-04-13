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
import tempfile
from typing import Any, Dict, List

MEMORY_SERVICE_URL = os.environ.get(
    "MEMORY_SERVICE_URL",
    "http://localhost:3031",
)

# Repo root is two levels up from this file (scripts/run_tests.py → repo root).
REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Proof surface definition
# ---------------------------------------------------------------------------

Step = Dict[str, Any]


DEFAULT_STEPS: List[Step] = [
    {
        "name": "HCA pipeline proof",
        "isolated_storage": True,
        "cmd": [
            sys.executable, "-m", "pytest",
            "tests/test_hca_pipeline.py", "-q",
        ],
    },
    {
        "name": "Backend local proof",
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
    {
        "name": "Backend full proof",
        "isolated_storage": True,
        "cmd": [
            sys.executable, "-m", "pytest",
            "backend/tests", "-q",
        ],
    },
]

SIDECAR_STEP: Step = {
    "name": "Live sidecar proof",
    "isolated_storage": True,
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


def _isolated_proof_env(storage_root: pathlib.Path) -> Dict[str, str]:
    return {
        "MEMORY_BACKEND": "python",
        "HCA_STORAGE_ROOT": str(storage_root),
        "MEMORY_STORAGE_DIR": str(storage_root / "memory"),
    }


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
    if step.get("isolated_storage") and "MEMORY_SERVICE_URL" not in extra_env:
        env.pop("MEMORY_SERVICE_URL", None)
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
                "    RUN_MEMVID_TESTS=1 python scripts/run_tests.py --sidecar"
            )
            return 1
        if not _check_sidecar_health():
            print(
                f"Sidecar mode requested, but health check failed at "
                f"{MEMORY_SERVICE_URL}/health\n"
                "Start the memvid sidecar first:\n"
                "    cargo run --manifest-path "
                "memvid_service/Cargo.toml --release"
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
