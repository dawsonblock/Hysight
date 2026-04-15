#!/usr/bin/env python3
"""Run the live Mongo proof against a disposable local Docker MongoDB."""

from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

from proof_receipt import write_proof_receipt


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_JUNIT_XML = (
    REPO_ROOT / "test_reports" / "pytest" / "backend-live-mongo-proof.xml"
)
DEFAULT_RECEIPT_PATH = (
    REPO_ROOT
    / "test_reports"
    / "proof_receipts"
    / "backend-live-mongo-proof.json"
)


def _run_command(
    command: list[str],
    *,
    env: dict[str, str] | None = None,
    capture_output: bool = False,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=capture_output,
        check=check,
    )


def _wait_for_tcp(host: str, port: int, timeout_seconds: float) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except OSError:
            time.sleep(0.5)
    return False


def _docker_logs(container_name: str) -> str:
    try:
        result = _run_command(
            ["docker", "logs", container_name],
            capture_output=True,
            check=False,
        )
    except FileNotFoundError:
        return "docker client is unavailable"
    return (result.stdout or "") + (result.stderr or "")


def _cleanup_container(container_name: str) -> None:
    try:
        _run_command(
            ["docker", "rm", "-f", container_name],
            check=False,
            capture_output=True,
        )
    except FileNotFoundError:
        return


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--container-name",
        default="hysight-live-mongo-proof",
    )
    parser.add_argument("--image", default=os.environ.get("LIVE_MONGO_IMAGE", "mongo:7"))
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("LIVE_MONGO_PORT", "27017")),
    )
    parser.add_argument(
        "--db-name",
        default=os.environ.get("LIVE_MONGO_DB_NAME", "hysight_live_proof"),
    )
    parser.add_argument(
        "--ready-timeout",
        type=float,
        default=float(os.environ.get("LIVE_MONGO_READY_TIMEOUT", "30")),
    )
    parser.add_argument("--receipt-path", type=Path, default=DEFAULT_RECEIPT_PATH)
    parser.add_argument("--junit-xml", type=Path, default=DEFAULT_JUNIT_XML)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    junit_xml = args.junit_xml
    junit_xml.parent.mkdir(parents=True, exist_ok=True)
    junit_xml.unlink(missing_ok=True)

    mongo_url = f"mongodb://127.0.0.1:{args.port}"
    command_label = "make proof-mongo-live"
    outcome = "failed"
    failure_reason = None
    exit_code = 1

    try:
        _run_command(["docker", "info"], capture_output=True)
        _cleanup_container(args.container_name)

        _run_command(
            [
                "docker",
                "run",
                "-d",
                "--rm",
                "--name",
                args.container_name,
                "-p",
                f"{args.port}:27017",
                args.image,
            ]
        )

        if not _wait_for_tcp("127.0.0.1", args.port, args.ready_timeout):
            failure_reason = (
                "Disposable MongoDB did not become reachable on "
                f"127.0.0.1:{args.port}.\n{_docker_logs(args.container_name)}"
            )
            print(failure_reason, file=sys.stderr)
            return 1

        env = dict(os.environ)
        pytest_addopts = env.get("PYTEST_ADDOPTS", "").strip()
        env["PYTEST_ADDOPTS"] = " ".join(
            part
            for part in (pytest_addopts, f"--junitxml={junit_xml}")
            if part
        )
        env["LIVE_MONGO_URL"] = mongo_url
        env["LIVE_MONGO_DB_NAME"] = args.db_name

        result = _run_command(["make", "test-mongo-live"], env=env, check=False)
        exit_code = result.returncode
        if exit_code == 0:
            outcome = "passed"
        else:
            failure_reason = (
                "Live Mongo proof failed. Inspect the pytest output above or "
                f"the JUnit report at {junit_xml}."
            )
        return exit_code
    except FileNotFoundError as exc:
        failure_reason = (
            f"{exc.filename or 'docker'} is unavailable. Install Docker and re-run, "
            "or use make test-mongo-live against an already running Mongo instance."
        )
        print(failure_reason, file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as exc:
        failure_reason = (
            f"Command failed before the live Mongo proof ran: {' '.join(exc.cmd)}"
        )
        print(failure_reason, file=sys.stderr)
        return exc.returncode or 1
    finally:
        write_proof_receipt(
            output_path=args.receipt_path,
            proof_tier="live-mongo",
            environment_mode="docker_disposable_local",
            service_connection_mode=f"docker:{args.image}",
            service_endpoint=mongo_url,
            command=command_label,
            junit_xml=junit_xml if junit_xml.exists() else None,
            outcome=outcome,
            failure_reason=failure_reason,
            metadata={
                "db_name": args.db_name,
                "container_name": args.container_name,
            },
        )
        _cleanup_container(args.container_name)


if __name__ == "__main__":
    sys.exit(main())