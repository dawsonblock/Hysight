"""Test configuration for pytest.

This file adjusts the import path so that the `hca` package and related modules
can be imported directly from the source tree without installation.  It adds
the repository root to `sys.path` before tests are collected.
"""

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
HCA = ROOT / "hca"

# Prepend the repository root and src to sys.path
for path in [str(ROOT), str(SRC), str(HCA)]:
    if path not in sys.path:
        sys.path.insert(0, path)