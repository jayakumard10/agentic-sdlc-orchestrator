"""Docker Compose default entrypoint: runs all three scenarios in sequence, so

`docker-compose up` alone produces a full, visible demonstration - clarification/
plan/merge gates (greenfield), impact review + a real retry + merge (brownfield),
re-planning + merge (ambiguous).

Each scenario gets its own fresh scratch copy of the shared target-app baseline
rather than all three sharing one cumulative workspace. Tried the cumulative
approach first (all three writing into the same live-served volume, so the running
target_app service would visibly evolve): it broke on the third scenario, because
the ambiguous fixture's captured app/main.py (recorded against a clean baseline)
silently overwrote the qr_router registration greenfield's own fixture had just
added, failing greenfield's own test_qr.py. Fixtures are captured independently
and were never validated to compose against each other's changes - correctness
across all three demos matters more than the live-reload narrative, so each
scenario is isolated. The target_app service therefore stays at its baseline
throughout this run; use scenarios/run_<scenario>.py individually against
/shared/target_app directly if you want to see one specific change land live.

Runs in replay mode by default (no login needed) - set ORCHESTRATOR_MODE=live to
use the real claude CLI instead (requires the host's ~/.claude bind-mounted in via
docker-compose.override.yml).
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from logging_config import configure_logging  # noqa: E402
from scenarios._runner import run_scenario  # noqa: E402

configure_logging()

_SCENARIOS_IN_ORDER = ["greenfield", "brownfield", "ambiguous"]
_SCRATCH_ROOT = Path("/tmp/scenario_runs")


def _fresh_scratch_copy(baseline: Path, scenario_type: str) -> Path:
    dest = _SCRATCH_ROOT / scenario_type
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(
        baseline, dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache", "*.db", ".git")
    )
    return dest


def main() -> None:
    baseline = Path(os.environ.get("TARGET_APP_WORKSPACE", "/shared/target_app"))
    live = os.environ.get("ORCHESTRATOR_MODE", "replay") == "live"

    for scenario_type in _SCENARIOS_IN_ORDER:
        print()
        print("=" * 70)
        print(f" SCENARIO: {scenario_type}")
        print("=" * 70)
        try:
            workspace = _fresh_scratch_copy(baseline, scenario_type)
            run_scenario(scenario_type, live=live, workspace=workspace)
        except Exception as exc:  # noqa: BLE001 - report and continue to the next demo
            print(f"!!! scenario '{scenario_type}' raised: {exc}")

    print()
    print("=== All scenarios complete. Orchestrator container exiting 0. ===")
    print("postgres and target_app keep running (at the baseline app) - inspect with:")
    print("  curl http://localhost:8000/health")
    print("Re-run a single scenario against the live shared volume directly with:")
    print(
        "  docker compose run --rm orchestrator python scenarios/run_greenfield.py "
        "(edit _runner.py's default workspace, or pass workspace=Path('/shared/target_app') manually)"
    )


if __name__ == "__main__":
    main()
