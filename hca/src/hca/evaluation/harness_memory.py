"""Memory evaluation harness."""

from __future__ import annotations

import shutil
import uuid
from typing import Any, Dict, List

from hca.common.enums import MemoryType
from hca.common.types import MemoryRecord
from hca.memory.episodic_store import EpisodicStore
from hca.memory.retrieval import retrieve
from hca.paths import run_storage_dir


def run_memory_harness() -> Dict[str, Any]:
    """Test memory retrieval and contradiction detection."""
    run_id = f"eval_memory_{uuid.uuid4().hex}"
    run_path = run_storage_dir(run_id)
    if run_path.exists():
        shutil.rmtree(run_path)

    store = EpisodicStore(run_id)
    store.append(
        MemoryRecord(
            run_id=run_id,
            memory_type=MemoryType.episodic,
            subject="keys",
            content="kitchen",
            confidence=0.9,
        )
    )
    store.append(
        MemoryRecord(
            run_id=run_id,
            memory_type=MemoryType.episodic,
            subject="weather",
            content="sunny",
            confidence=0.6,
        )
    )

    results = retrieve(run_id, "keys")
    retrieval_passed = (
        len(results) > 0 and results[0].record.content == "kitchen"
    )

    store.append(
        MemoryRecord(
            run_id=run_id,
            memory_type=MemoryType.episodic,
            subject="keys",
            content="car",
            confidence=0.7,
        )
    )

    results = retrieve(run_id, "keys")
    contradiction_passed = any(result.contradiction for result in results)
    strict_results = retrieve(run_id, "weather", max_staleness=0.2)
    freshness_filter_passed = len(strict_results) == 1

    cases: List[Dict[str, Any]] = [
        {
            "name": "retrieval_subject_match",
            "passed": retrieval_passed,
            "top_subject": results[0].record.subject if results else None,
        },
        {
            "name": "contradiction_detection",
            "passed": contradiction_passed,
            "contradictions": len(
                [result for result in results if result.contradiction]
            ),
        },
        {
            "name": "freshness_filter",
            "passed": freshness_filter_passed,
            "filtered_count": len(strict_results),
        },
    ]

    return {
        "harness": "memory",
        "cases": cases,
        "metrics": {
            "retrieval_precision": 1.0 if retrieval_passed else 0.0,
            "contradiction_detection_rate": (
                1.0 if contradiction_passed else 0.0
            ),
            "freshness_filter_rate": (
                1.0 if freshness_filter_passed else 0.0
            ),
        },
    }


def run() -> dict:
    """Entry point for CLI."""
    return run_memory_harness()
