"""Ambiguous demo: a vague requirement that triggers mid-flight re-planning.

Exercises: Requirement Clarifier surfaces ambiguity in "make the service more
reliable" -> Codebase Reasoner's deterministic conflict check finds existing
rate-limiting middleware and sets replanning_triggered -> Decomposer/Planner's
initial plan -> Re-planner (replanning_approval gate) -> Decomposer/Planner
produces a genuinely revised plan (T0 reconciliation task) -> Coder -> Test
Executor || Documentation -> Release Readiness Gate (merge_release_approval gate).

Usage: python orchestrator/scenarios/run_ambiguous.py [--live]
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
    run_scenario("ambiguous", live=args.live)
