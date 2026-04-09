"""Smoke test CLI for the hybrid cognitive agent."""

import argparse

from hca.runtime.runtime import Runtime


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a smoke test of the hybrid cognitive agent.")
    parser.add_argument("goal", nargs="?", default="echo greeting", help="Goal description for the run")
    args = parser.parse_args()
    runtime = Runtime()
    run_id = runtime.run(args.goal)
    print(f"Run {run_id} completed.")


if __name__ == "__main__":
    main()