#!/usr/bin/env python3
"""Run the live memvid sidecar proof with lifecycle management and receipts."""

from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LOG_PATH = REPO_ROOT / "test_reports" / "proof-sidecar.log"
BOOTSTRAP_HINT = "See BOOTSTRAP.md for the supported bootstrap path."
DEFAULT_SIDECAR_PORT = 3031
AUTO_FALLBACK_PORT_LIMIT = 10


def _default_service_url(port: int) -> str:
    return f"http://localhost:{port}"


def _uses_default_local_target(service_url: str, port: int) -> bool:
    normalized_url = service_url.rstrip("/")
    if port != DEFAULT_SIDECAR_PORT:
        return False
    return normalized_url in {
        _default_service_url(DEFAULT_SIDECAR_PORT),
        f"http://127.0.0.1:{DEFAULT_SIDECAR_PORT}",
    }


def _next_available_port(start_port: int) -> int | None:
    end_port = start_port + AUTO_FALLBACK_PORT_LIMIT
    for candidate in range(start_port, end_port):
        if _port_is_available(candidate):
            return candidate
    return None


def _resolve_service_target(service_url: str, port: int) -> tuple[str, int, str | None, str | None]:
    if not _uses_default_local_target(service_url, port):
        return service_url, port, None, None

    default_health_url = f"{service_url.rstrip('/')}/health"
    if _check_health(service_url):
        conflict_reason = (
            f"Default proof endpoint {default_health_url} is already healthy and in use."
        )
    elif not _port_is_available(port):
        conflict_reason = (
            f"Default proof port {port} is already in use, and {default_health_url} is unhealthy."
        )
    else:
        return service_url, port, None, None

    fallback_port = _next_available_port(port + 1)
    if fallback_port is None:
        failure_reason = (
            f"{conflict_reason} No free fallback localhost port was found in the range "
            f"{port + 1}-{port + AUTO_FALLBACK_PORT_LIMIT}. Stop the conflicting service or rerun "
            "with an explicit MEMORY_SERVICE_PORT."
        )
        return service_url, port, None, failure_reason

    fallback_url = _default_service_url(fallback_port)
    notice = (
        f"{conflict_reason} Falling back to {fallback_url} for this proof run."
    )
    return fallback_url, fallback_port, notice, None


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


def _port_is_available(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as candidate:
        candidate.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            candidate.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


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
        default=int(os.environ.get("MEMORY_SERVICE_PORT", str(DEFAULT_SIDECAR_PORT))),
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
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help=(
            "Absolute directory for the sidecar memory data root. When unset, "
            "proof uses an isolated temporary directory."
        ),
    )
    parser.add_argument("--log-path", type=Path, default=DEFAULT_LOG_PATH)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    service_url = args.service_url.strip() or _default_service_url(args.port)
    service_url, selected_port, fallback_notice, fallback_failure = _resolve_service_target(
        service_url,
        args.port,
    )
    args.log_path.parent.mkdir(parents=True, exist_ok=True)

    sidecar_process: subprocess.Popen[str] | None = None
    data_dir_handle: tempfile.TemporaryDirectory[str] | None = None
    log_handle = None

    if args.data_dir is not None:
        data_dir = args.data_dir.expanduser().resolve()
        data_dir.mkdir(parents=True, exist_ok=True)
    else:
        data_dir_handle = tempfile.TemporaryDirectory(
            prefix="hysight-sidecar-proof-"
        )
        data_dir = Path(data_dir_handle.name).resolve()

    try:
        if fallback_failure is not None:
            print(fallback_failure, file=sys.stderr)
            return 1

        if fallback_notice is not None:
            print(fallback_notice, file=sys.stderr)

        if _check_health(service_url):
            failure_reason = (
                f"Refusing to reuse an already-running memvid sidecar at {service_url}. "
                "Use make test-sidecar for an existing service or override MEMORY_SERVICE_PORT."
            )
            print(failure_reason, file=sys.stderr)
            return 1

        if not _port_is_available(selected_port):
            failure_reason = (
                f"Port {selected_port} is already in use, but {service_url}/health is not healthy. "
                "Stop the conflicting process or rerun with a free port, for example "
                "MEMORY_SERVICE_PORT=3032 make proof-sidecar."
            )
            print(failure_reason, file=sys.stderr)
            return 1

        args.log_path.unlink(missing_ok=True)
        log_handle = args.log_path.open("w", encoding="utf-8")
        env = dict(os.environ)
        env["MEMORY_SERVICE_PORT"] = str(selected_port)
        env["MEMORY_DATA_DIR"] = str(data_dir)
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
        proof_env["MEMORY_SERVICE_PORT"] = str(selected_port)
        proof_env["RUN_MEMVID_TESTS"] = "1"
        proof_env["MEMORY_BACKEND"] = "rust"
        proof_env["MEMORY_DATA_DIR"] = str(data_dir)
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
        if data_dir_handle is not None:
            data_dir_handle.cleanup()


if __name__ == "__main__":
    sys.exit(main())