"""One-time, host-only build tool: drives the real orchestrator graph in live mode

against the authenticated `claude` CLI, then writes the resulting Coder attempts and
the real human gate decisions made during capture to
orchestrator/fixtures/<scenario>/transcript.json for replay.

Never runs inside Docker - the operator's OAuth session lives on the host and
fixture capture is a build-time activity the reviewer-facing stack never needs
(see the credential-boundary note in docs/architecture.md).

Usage: python scripts/capture_fixture.py <greenfield|brownfield|ambiguous>
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

_ORCHESTRATOR_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ORCHESTRATOR_ROOT))

from langgraph.types import Command  # noqa: E402

from checkpointer import build_memory_checkpointer  # noqa: E402
from graph import build_graph  # noqa: E402
from state import GraphState  # noqa: E402

_REPO_ROOT = _ORCHESTRATOR_ROOT.parent
_FIXTURES_DIR = _ORCHESTRATOR_ROOT / "fixtures"
_CAPTURE_WORKSPACE_ROOT = _REPO_ROOT / ".fixture_capture_workspace"

SCENARIOS: dict[str, dict] = {
    "greenfield": {
        "requirement_raw": (
            "Add a QR code generation endpoint for shortened URLs, returning a PNG "
            "the client can embed."
        ),
        "decisions": {
            "clarification_approval": {
                "status": "approved",
                "clarified_requirement": (
                    "Add a GET /{code}/qr endpoint that returns a PNG QR code encoding "
                    "the short URL's redirect target, as a new app/qr.py module with no "
                    "changes to existing endpoints."
                ),
                "decided_by": "human",
            },
            "plan_approval": {"status": "approved", "decided_by": "human"},
            "merge_release_approval": {"status": "approved", "decided_by": "human"},
        },
    },
    "brownfield": {
        "requirement_raw": (
            "The click-analytics counter under-counts on concurrent redirects; make "
            "it thread-/process-safe."
        ),
        "decisions": {
            "codebase_impact_review": {"status": "approved", "decided_by": "human"},
            "merge_release_approval": {"status": "approved", "decided_by": "human"},
        },
    },
    "ambiguous": {
        "requirement_raw": "Make the service more reliable.",
        "decisions": {
            "replanning_approval": {"status": "approved", "decided_by": "human"},
            "merge_release_approval": {"status": "approved", "decided_by": "human"},
        },
    },
}


def _seed_workspace(scenario_type: str) -> Path:
    workspace = _CAPTURE_WORKSPACE_ROOT / scenario_type
    if workspace.exists():
        shutil.rmtree(workspace, ignore_errors=True)
    shutil.copytree(
        _REPO_ROOT / "target_app",
        workspace,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache", "*.db"),
    )
    return workspace


def capture(scenario_type: str) -> None:
    scenario = SCENARIOS[scenario_type]
    workspace = _seed_workspace(scenario_type)
    compiled = build_graph(workspace, _FIXTURES_DIR, build_memory_checkpointer())
    config = {"configurable": {"thread_id": f"capture-{scenario_type}"}}

    result = compiled.invoke(
        GraphState(
            scenario_type=scenario_type,
            requirement_raw=scenario["requirement_raw"],
            mode="live",
        ),
        config=config,
    )

    gate_log: list[dict] = []
    steps = 0
    while "__interrupt__" in result and steps < 20:
        steps += 1
        payload = result["__interrupt__"][0].value
        gate_type = payload["gate_type"]
        decision = scenario["decisions"][gate_type]
        print(f"  [gate] {gate_type} -> {decision['status']}")
        gate_log.append({"gate_type": gate_type, "payload": payload, "decision": decision})
        result = compiled.invoke(Command(resume=decision), config=config)

    if "__interrupt__" in result:
        raise RuntimeError(
            f"scenario '{scenario_type}' still paused after {steps} resumes - "
            "a gate type is missing from SCENARIOS[...]['decisions']"
        )

    attempts = [
        {
            "attempt_number": attempt.attempt_number,
            "code_files": attempt.code_files,
            "rationale": attempt.rationale,
        }
        for attempt in result["coder_attempts"]
    ]

    transcript = {
        "scenario_type": scenario_type,
        "requirement_raw": scenario["requirement_raw"],
        "attempts": attempts,
        "gates": {entry["gate_type"]: entry["decision"] for entry in gate_log},
        "gate_log": gate_log,
        "final_run_status": result["run_status"],
    }

    out_dir = _FIXTURES_DIR / scenario_type
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "transcript.json").write_text(
        json.dumps(transcript, indent=2, default=str), encoding="utf-8"
    )
    print(
        f"captured '{scenario_type}': {len(attempts)} attempt(s), "
        f"run_status={result['run_status']}, retry_count={result['retry_count']}"
    )


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in SCENARIOS:
        print(f"usage: python {sys.argv[0]} <{'|'.join(SCENARIOS)}>", file=sys.stderr)
        raise SystemExit(1)
    capture(sys.argv[1])
