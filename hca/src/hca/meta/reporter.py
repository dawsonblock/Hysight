"""Experimental report-generation stub.

This helper is non-authoritative and separate from the replay-backed run
artifacts produced by the active runtime.
"""

from typing import Dict, Any


def generate_report(context: Dict[str, Any]) -> str:
    """Return a simple textual report summarising the run."""
    return "Run completed successfully."