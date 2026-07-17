"""Greenfield demo: add a QR-code endpoint to a service that doesn't have one yet.

Exercises: Requirement Clarifier (clarification_approval gate) -> conditional skip
of Codebase Reasoner (no existing code to reason about) -> Architecture/Design ->
Decomposer/Planner (plan_approval gate) -> Coder -> Test Executor || Documentation
-> Release Readiness Gate (merge_release_approval gate).

Usage: python orchestrator/scenarios/run_greenfield.py [--live]
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
    run_scenario("greenfield", live=args.live)
