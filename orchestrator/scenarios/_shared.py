"""Shared scenario configuration used by both the fixture-capture tool

(scripts/capture_fixture.py) and the replay-mode demo entry points (run_*.py in
this package). The requirement text and any pre-seeded files must be identical
between capture and replay - otherwise replay would present different initial
conditions than what was actually captured, breaking the whole point of replay
fidelity.
"""

from __future__ import annotations

import shutil
from pathlib import Path

_ORCHESTRATOR_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = _ORCHESTRATOR_ROOT.parent
FIXTURES_DIR = _ORCHESTRATOR_ROOT / "fixtures"

SCENARIO_REQUIREMENTS: dict[str, str] = {
    "greenfield": (
        "Add a QR code generation endpoint for shortened URLs, returning a PNG "
        "the client can embed."
    ),
    "brownfield": (
        "The click-analytics counter under-counts on concurrent redirects; make "
        "it thread-/process-safe."
    ),
    "ambiguous": "Make the service more reliable.",
}

# QA-style regression test that already exists in the brownfield codebase before
# the fix request comes in - see scripts/scenario_seeds/brownfield_test_concurrency.py
# for why this needs real PostgreSQL rather than the SQLite the baseline suite uses.
SCENARIO_SEED_FILES: dict[str, dict[str, Path]] = {
    "brownfield": {
        "tests/test_concurrency.py": (
            _ORCHESTRATOR_ROOT
            / "scripts"
            / "scenario_seeds"
            / "brownfield_test_concurrency.py"
        ),
    },
}


def seed_workspace(scenario_type: str, dest_root: Path) -> Path:
    """Create a fresh, uniquely-named workspace under dest_root seeded from

    target_app plus any scenario-specific seed files. Never deletes/reuses an
    existing path - see capture_fixture.py's docstring for why that was unreliable
    on Windows.
    """
    dest_root.mkdir(parents=True, exist_ok=True)
    workspace = dest_root / scenario_type
    suffix = 0
    while workspace.exists():
        suffix += 1
        workspace = dest_root / f"{scenario_type}_{suffix}"

    shutil.copytree(
        REPO_ROOT / "target_app",
        workspace,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache", "*.db"),
    )
    for relative_dest, source_path in SCENARIO_SEED_FILES.get(scenario_type, {}).items():
        dest = workspace / relative_dest
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(Path(source_path).read_text(encoding="utf-8"), encoding="utf-8")
    return workspace
