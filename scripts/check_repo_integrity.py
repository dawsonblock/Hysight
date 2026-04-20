#!/usr/bin/env python3
"""Fail fast when repo-critical proof and bootstrap files drift or disappear."""

from __future__ import annotations

import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent

REQUIRED_FILES = [
    "BOOTSTRAP.md",
    "Makefile",
    "README.md",
    "pyproject.toml",
    ".github/workflows/backend-proof.yml",
    ".github/workflows/frontend-proof.yml",
    "backend/requirements-core.txt",
    "backend/requirements-test.txt",
    "backend/requirements-integration.txt",
    "contract/schema.json",
    "frontend/package.json",
    "frontend/scripts/verify-runtime.js",
    "frontend/src/lib/api.fixtures.generated.json",
    "frontend/yarn.lock",
    "scripts/run_tests.py",
    "scripts/run_backend.sh",
    "scripts/launch_unified.sh",
    "scripts/check_repo_integrity.py",
    "scripts/proof_frontend.py",
    "scripts/proof_receipt.py",
    "scripts/proof_mongo_live.py",
    "scripts/proof_sidecar.py",
    "scripts/export_api_fixtures.py",
]

REQUIRED_MAKE_TARGETS = [
    "venv",
    "dev",
    "test",
    "test-bootstrap-frontend",
    "test-pipeline",
    "test-contract",
    "test-backend-baseline",
    "test-backend-integration",
    "proof-frontend",
    "proof-mongo-live",
    "test-mongo-live",
    "proof-sidecar",
    "test-sidecar",
    "test-fixture-drift",
]

REQUIRED_PYTEST_MARKERS = [
    "baseline",
    "integration",
    "live",
    "fixture_drift",
]


def _missing_files() -> list[str]:
    return [
        path
        for path in REQUIRED_FILES
        if not (REPO_ROOT / path).exists()
    ]


def _missing_make_targets() -> list[str]:
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
    missing = []
    for target in REQUIRED_MAKE_TARGETS:
        pattern = re.compile(rf"(?m)^{re.escape(target)}:(?:\s|$)")
        if not pattern.search(makefile):
            missing.append(target)
    return missing


def _missing_markers() -> list[str]:
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    missing = []
    for marker in REQUIRED_PYTEST_MARKERS:
        if f'"{marker}:' not in pyproject:
            missing.append(marker)
    return missing


def main() -> int:
    missing_files = _missing_files()
    missing_targets = _missing_make_targets()
    missing_markers = _missing_markers()

    if not any((missing_files, missing_targets, missing_markers)):
        print("Repo integrity check passed.")
        return 0

    if missing_files:
        print("Missing required files:", file=sys.stderr)
        for path in missing_files:
            print(f" - {path}", file=sys.stderr)

    if missing_targets:
        print("Missing required Make targets:", file=sys.stderr)
        for target in missing_targets:
            print(f" - {target}", file=sys.stderr)

    if missing_markers:
        print("Missing required pytest markers:", file=sys.stderr)
        for marker in missing_markers:
            print(f" - {marker}", file=sys.stderr)

    return 1


if __name__ == "__main__":
    raise SystemExit(main())