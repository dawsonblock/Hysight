"""Bounded subprocess execution for allowlisted local commands."""

from __future__ import annotations

import os
import signal
import subprocess
import time
from pathlib import Path
from typing import Any, Sequence


class CommandPolicyError(RuntimeError):
    """Raised when a command violates sandbox policy."""


class CommandTimeoutError(RuntimeError):
    """Raised when a command exceeds the allowed timeout."""


def allowlisted_commands() -> list[str]:
    return [
        "pytest",
        "python -m pytest",
        "python3 -m pytest",
        "cargo test",
        "cargo check",
        "git status|diff|log|show",
    ]


def _normalize_output(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _truncate_output(text: str, max_output_chars: int) -> tuple[str, bool]:
    if len(text) <= max_output_chars:
        return text, False

    marker = "\n...[truncated]..."
    keep = max_output_chars - len(marker)
    if keep <= 0:
        return marker[:max_output_chars], True
    return text[:keep] + marker, True


def _validate_command(argv: Sequence[str]) -> list[str]:
    if not argv:
        raise CommandPolicyError("argv must contain at least one element")

    command = argv[0]
    if command == "pytest":
        return list(argv)

    if command in {"python", "python3"}:
        if len(argv) >= 3 and list(argv[1:3]) == ["-m", "pytest"]:
            return list(argv)
        raise CommandPolicyError(
            "Only python -m pytest is allowlisted"
        )

    if command == "cargo":
        if len(argv) >= 2 and argv[1] in {"test", "check"}:
            return list(argv)
        raise CommandPolicyError(
            "Only cargo test and cargo check are allowlisted"
        )

    if command == "git":
        if len(argv) >= 2 and argv[1] in {"status", "diff", "log", "show"}:
            return list(argv)
        raise CommandPolicyError(
            "Only git status, diff, log, and show are allowlisted"
        )

    raise CommandPolicyError(f"Command '{command}' is not allowlisted")


def _validate_cwd(cwd: Path, repo_root: Path) -> Path:
    resolved_repo_root = repo_root.resolve()
    resolved_cwd = cwd.resolve()
    if not (
        resolved_cwd == resolved_repo_root
        or resolved_repo_root in resolved_cwd.parents
    ):
        raise CommandPolicyError(
            "cwd must stay within the repository root"
        )
    return resolved_cwd


def _sandbox_env() -> dict[str, str]:
    allowed_keys = {
        "PATH",
        "HOME",
        "USER",
        "TMPDIR",
        "TMP",
        "TEMP",
        "LANG",
        "LC_ALL",
        "TERM",
    }
    env = {
        key: value
        for key, value in os.environ.items()
        if key in allowed_keys
    }
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def run_in_sandbox(
    argv: Sequence[str],
    *,
    cwd: Path,
    repo_root: Path,
    timeout_seconds: int,
    max_output_chars: int = 12_000,
) -> dict[str, Any]:
    validated_argv = _validate_command(argv)
    validated_cwd = _validate_cwd(cwd, repo_root)

    started = time.monotonic()
    process: subprocess.Popen[str] | None = None
    stdout_raw: Any = ""
    stderr_raw: Any = ""
    try:
        process = subprocess.Popen(
            validated_argv,
            cwd=str(validated_cwd),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=False,
            env=_sandbox_env(),
            start_new_session=True,
        )
        assert process is not None
        stdout_raw, stderr_raw = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        if process is not None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            stdout_raw, stderr_raw = process.communicate()
        else:
            stdout_raw, stderr_raw = exc.stdout, exc.stderr
        stdout, stdout_truncated = _truncate_output(
            _normalize_output(stdout_raw),
            max_output_chars,
        )
        stderr, stderr_truncated = _truncate_output(
            _normalize_output(stderr_raw),
            max_output_chars,
        )
        raise CommandTimeoutError(
            "Command timed out after "
            f"{timeout_seconds}s. stdout={stdout!r} stderr={stderr!r} "
            f"truncated={stdout_truncated or stderr_truncated}"
        ) from exc

    duration_seconds = round(time.monotonic() - started, 3)
    stdout, stdout_truncated = _truncate_output(
        _normalize_output(stdout_raw),
        max_output_chars,
    )
    stderr, stderr_truncated = _truncate_output(
        _normalize_output(stderr_raw),
        max_output_chars,
    )

    return {
        "argv": validated_argv,
        "cwd": str(validated_cwd),
        "returncode": 0 if process is None else process.returncode,
        "stdout": stdout,
        "stderr": stderr,
        "ok": False if process is None else process.returncode == 0,
        "truncated": stdout_truncated or stderr_truncated,
        "duration_seconds": duration_seconds,
    }
