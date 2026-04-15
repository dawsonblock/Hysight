#!/usr/bin/env python3
"""Run the live memvid sidecar proof with lifecycle management and receipts."""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LOG_PATH = REPO_ROOT / "test_reports" / "proof-sidecar.log"
BOOTSTRAP_HINT = "See BOOTSTRAP.md for the supported bootstrap path."


def _check_health(url: str) -> bool:
    try:
        with urlopen(f"{url.rstrip('/')}/health", timeout=2) as response:
            return 200 <= response.status < 300
    except (URLError, ValueError, OSError):
        return False


def _wait_for_health(url: str, timeout_seconds: float) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if _check_health(url):
            return True
        time.sleep(1)
    return False


def _tail_log(log_path: Path, lines: int = 40) -> str:
    if not log_path.exists():
        return "sidecar log file does not exist"
    content = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(content[-lines:])


def _stop_process(process: subprocess.Popen[str] | None) -> None:
    if process is None:
        return
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("MEMORY_SERVICE_PORT", "3031")),
    )
    parser.add_argument(
        "--service-url",
        default=os.environ.get("MEMORY_SERVICE_URL", ""),
    )
    parser.add_argument(
        "--ready-timeout",
        type=float,
        default=float(os.environ.get("MEMORY_SERVICE_READY_TIMEOUT", "90")),
    )
    parser.add_argument("--log-path", type=Path, default=DEFAULT_LOG_PATH)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    service_url = args.service_url.strip() or f"http://localhost:{args.port}"
    args.log_path.parent.mkdir(parents=True, exist_ok=True)

    sidecar_process: subprocess.Popen[str] | None = None
    log_handle = None

    try:
        if _check_health(service_url):
            failure_reason = (
                f"Refusing to reuse an already-running memvid sidecar at {service_url}. "
                "Use make test-sidecar for an existing service or override MEMORY_SERVICE_PORT."
            )
            print(failure_reason, file=sys.stderr)
            return 1

        args.log_path.unlink(missing_ok=True)
        log_handle = args.log_path.open("w", encoding="utf-8")
        env = dict(os.environ)
        env["MEMORY_SERVICE_PORT"] = str(args.port)
        sidecar_process = subprocess.Popen(
            [
                "cargo",
                "run",
                "--manifest-path",
                "memvid_service/Cargo.toml",
                "--release",
            ],
            cwd=REPO_ROOT,
            env=env,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
        )

        if not _wait_for_health(service_url, args.ready_timeout):
            failure_reason = (
                f"memvid sidecar did not become healthy at {service_url}/health.\n"
                f"{_tail_log(args.log_path)}"
            )
            print(failure_reason, file=sys.stderr)
            return 1

        proof_env = dict(os.environ)
        proof_env["MEMORY_SERVICE_URL"] = service_url
        proof_env["MEMORY_SERVICE_PORT"] = str(args.port)
        proof_env["RUN_MEMVID_TESTS"] = "1"
        proof_env["MEMORY_BACKEND"] = "rust"
        proof_env["HYSIGHT_PROOF_ENVIRONMENT_MODE"] = "cargo_local_sidecar"
        proof_env["HYSIGHT_PROOF_SERVICE_CONNECTION_MODE"] = (
            "cargo-run:memvid_service"
        )

        result = subprocess.run(
            [sys.executable, "scripts/run_tests.py", "--sidecar"],
            cwd=REPO_ROOT,
            env=proof_env,
            text=True,
            check=False,
        )
        return result.returncode
    except FileNotFoundError as exc:
        failure_reason = (
            f"{exc.filename or 'cargo'} is unavailable. Install the Rust toolchain and re-run, "
            "or use make test-sidecar against an already running sidecar. "
            f"{BOOTSTRAP_HINT}"
        )
        print(failure_reason, file=sys.stderr)
        return 1
    finally:
        if log_handle is not None:
            log_handle.flush()
        if log_handle is not None:
            log_handle.close()
        _stop_process(sidecar_process)


if __name__ == "__main__":
    sys.exit(main())