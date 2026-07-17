"""Brownfield demo: fix a real concurrency bug in existing code.

Exercises: Codebase Reasoner (impact analysis, codebase_impact_review gate) ->
Architecture/Design -> Decomposer/Planner -> Coder -> Test Executor - first attempt
deliberately fails a pre-seeded concurrency regression test, driving a real bounded
retry (Coder retries, Test Executor re-runs, succeeds) -> Documentation ->
Release Readiness Gate (merge_release_approval gate) -> real git commit.

Requires PostgreSQL reachable (POSTGRES_* env vars) - the seeded concurrency test
needs a real MVCC database to reproduce the race; it will SKIP (not fail) without
one, which means the retry arc won't be exercised, just replayed as a no-op.

Usage: python orchestrator/scenarios/run_brownfield.py [--live]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scenarios._runner import run_scenario  # noqa: E402

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live",
        action="store_true",
        help="Use the real claude CLI and prompt for real gate decisions instead of replaying the captured fixture.",
    )
    args = parser.parse_args()
    run_scenario("brownfield", live=args.live)
