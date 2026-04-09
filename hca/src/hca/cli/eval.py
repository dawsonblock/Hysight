"""Evaluation CLI for the hybrid cognitive agent."""

from __future__ import annotations

import argparse
import json
from typing import Any, Dict

from hca.evaluation.harness_coordination import run as run_coordination
from hca.evaluation.harness_metacognition import run as run_metacognition
from hca.evaluation.harness_memory import run as run_memory
from hca.evaluation.harness_proactivity import run as run_proactivity
from hca.evaluation.harness_embodiment import run as run_embodiment
from hca.evaluation.harness_audit import run as run_audit
from hca.evaluation.metrics import compute_metrics


HARNESS_MAP = {
    "coordination": run_coordination,
    "metacognition": run_metacognition,
    "memory": run_memory,
    "proactivity": run_proactivity,
    "embodiment": run_embodiment,
    "audit": run_audit,
}


def _run_one(name: str) -> Dict[str, Any]:
    result = HARNESS_MAP[name]()
    return {
        "result": result,
        "metrics": compute_metrics(result),
    }


def _run_all() -> Dict[str, Any]:
    results = {name: _run_one(name) for name in HARNESS_MAP}
    metric_sets = [entry["metrics"] for entry in results.values()]
    aggregate_pass_rates = [
        metrics["pass_rate"]
        for metrics in metric_sets
        if "pass_rate" in metrics
    ]
    return {
        "results": results,
        "metrics": {
            "harness_count": len(results),
            "average_pass_rate": (
                sum(aggregate_pass_rates) / len(aggregate_pass_rates)
                if aggregate_pass_rates
                else 0.0
            ),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run evaluation harnesses for the hybrid cognitive agent."
    )
    parser.add_argument(
        "harness",
        nargs="?",
        default="coordination",
        choices=[*HARNESS_MAP.keys(), "all"],
        help="Which harness to run",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print structured JSON instead of a compact text summary.",
    )
    args = parser.parse_args()
    payload = _run_all() if args.harness == "all" else _run_one(args.harness)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True, default=str))
        return

    if args.harness == "all":
        print("Evaluation summary")
        print(json.dumps(payload["metrics"], indent=2, sort_keys=True))
        for name, entry in payload["results"].items():
            print(f"{name}: {json.dumps(entry['metrics'], sort_keys=True)}")
        return

    print(json.dumps(payload["metrics"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
