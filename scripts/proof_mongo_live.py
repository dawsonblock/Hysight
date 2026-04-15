#!/usr/bin/env python3
"""Run the live Mongo proof against a disposable local Docker MongoDB."""

from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import time
from importlib import import_module
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BOOTSTRAP_HINT = "See BOOTSTRAP.md for the supported bootstrap path."


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


def _wait_for_mongo_ping(mongo_url: str, timeout_seconds: float) -> bool:
    try:
        pymongo = import_module("pymongo")
    except Exception:
        return True

    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        client = None
        try:
            client = pymongo.MongoClient(
                mongo_url,
                serverSelectionTimeoutMS=1000,
            )
            client.admin.command("ping")
            return True
        except Exception:
            time.sleep(0.5)
        finally:
            try:
                if client is not None:
                    client.close()
            except Exception:
                pass
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
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    mongo_url = f"mongodb://127.0.0.1:{args.port}"

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

        if not _wait_for_mongo_ping(mongo_url, args.ready_timeout):
            failure_reason = (
                "Disposable MongoDB accepted TCP connections but did not answer "
                f"ping at {mongo_url}.\n{_docker_logs(args.container_name)}"
            )
            print(failure_reason, file=sys.stderr)
            return 1

        env = dict(os.environ)
        env["RUN_MONGO_TESTS"] = "1"
        env["MONGO_URL"] = mongo_url
        env["DB_NAME"] = args.db_name
        env["HYSIGHT_PROOF_ENVIRONMENT_MODE"] = "docker_disposable_local"
        env["HYSIGHT_PROOF_SERVICE_CONNECTION_MODE"] = f"docker:{args.image}"

        result = _run_command(
            [sys.executable, "scripts/run_tests.py", "--mongo-live"],
            env=env,
            check=False,
        )
        return result.returncode
    except FileNotFoundError as exc:
        failure_reason = (
            f"{exc.filename or 'docker'} is unavailable. Install Docker and re-run, "
            "or use make test-mongo-live against an already running Mongo instance. "
            f"{BOOTSTRAP_HINT}"
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
        _cleanup_container(args.container_name)


if __name__ == "__main__":
    sys.exit(main())