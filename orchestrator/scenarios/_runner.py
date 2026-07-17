"""Shared driver for the three scenario demo entry points.

Handles workspace seeding, checkpointer selection, dual JSONL/console telemetry, and
the interrupt/resume loop for both modes: replay (feeds back each gate's recorded
decision from the fixture) and live (prompts a real human at the terminal). The
compiled graph runs an identical code path either way - only who answers the
interrupt differs.
"""

from __future__ import annotations

import json
import os
import sys
import time
from contextlib import ExitStack
from pathlib import Path

_ORCHESTRATOR_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ORCHESTRATOR_ROOT))

from langgraph.types import Command  # noqa: E402

from checkpointer import build_memory_checkpointer, build_postgres_checkpointer  # noqa: E402
from graph import build_graph  # noqa: E402
from metrics import compute_metrics, summarize_run  # noqa: E402
from scenarios._shared import FIXTURES_DIR, REPO_ROOT, SCENARIO_REQUIREMENTS, seed_workspace  # noqa: E402
from state import GraphState  # noqa: E402
from telemetry import TelemetrySink  # noqa: E402

_RUN_WORKSPACE_ROOT = REPO_ROOT / ".scenario_runs"
_TELEMETRY_DIR = _RUN_WORKSPACE_ROOT / "telemetry"
_MAX_GATE_RESUMES = 20


def _load_fixture_gates(scenario_type: str) -> dict[str, dict]:
    fixture_path = FIXTURES_DIR / scenario_type / "transcript.json"
    if not fixture_path.is_file():
        return {}
    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    return data.get("gates", {})


def _prompt_live_decision(gate_type: str, payload: dict) -> dict:
    print(f"\n--- HUMAN APPROVAL REQUIRED: {gate_type} ---")
    print(json.dumps(payload, indent=2, default=str))
    while True:
        raw = input("Approve this? [y/n]: ").strip().lower()
        if raw in ("y", "yes"):
            return {"status": "approved", "decided_by": "human"}
        if raw in ("n", "no"):
            return {"status": "rejected", "decided_by": "human"}
        print("Please answer y or n.")


def run_scenario(scenario_type: str, live: bool = False, workspace: Path | None = None) -> None:
    """Run one scenario. If `workspace` is given, operate on it directly (no

    seeding/copying) - used by run_all_scenarios.py's Docker Compose entrypoint,
    which points all three scenarios at the same shared volume the target_app
    container serves, so each demo's changes are visible in the live service.
    Standalone entry points (run_greenfield.py etc.) leave this unset and get an
    isolated, reproducible scratch copy via seed_workspace() instead.
    """
    mode = "live" if live else "replay"
    print(f"=== Running '{scenario_type}' scenario in {mode} mode ===")

    if workspace is None:
        workspace = seed_workspace(scenario_type, _RUN_WORKSPACE_ROOT)
    print(f"Workspace: {workspace}")

    run_id = f"{scenario_type}-{int(time.time())}"
    telemetry_path = _TELEMETRY_DIR / f"{run_id}.jsonl"
    sink = TelemetrySink(telemetry_path)

    with ExitStack() as stack:
        if os.environ.get("POSTGRES_USER"):
            checkpointer = stack.enter_context(build_postgres_checkpointer())
        else:
            checkpointer = build_memory_checkpointer()

        compiled = build_graph(workspace, FIXTURES_DIR, checkpointer)
        config = {"configurable": {"thread_id": run_id}}
        recorded_gates = _load_fixture_gates(scenario_type) if not live else {}

        result = compiled.invoke(
            GraphState(
                scenario_type=scenario_type,
                requirement_raw=SCENARIO_REQUIREMENTS[scenario_type],
                mode=mode,
            ),
            config=config,
        )
        for line in sink.flush_new_events(result["events"]):
            print(line)

        steps = 0
        while "__interrupt__" in result and steps < _MAX_GATE_RESUMES:
            steps += 1
            payload = result["__interrupt__"][0].value
            gate_type = payload["gate_type"]

            if live:
                decision = _prompt_live_decision(gate_type, payload)
            else:
                decision = recorded_gates.get(gate_type)
                if decision is None:
                    raise RuntimeError(
                        f"replay mode: no recorded decision for gate '{gate_type}' - "
                        "this input has no matching fixture data"
                    )
                print(f"\n--- GATE (replayed from fixture): {gate_type} -> {decision['status']} ---")

            result = compiled.invoke(Command(resume=decision), config=config)
            for line in sink.flush_new_events(result["events"]):
                print(line)

        if "__interrupt__" in result:
            raise RuntimeError(
                f"scenario '{scenario_type}' still paused after {steps} resumes - "
                "a gate type has no recorded decision in this fixture"
            )

        print()
        print(f"=== Run finished: run_status={result['run_status']} ===")
        print(
            f"retry_count={result['retry_count']} "
            f"rollback_count={result['rollback_count']} "
            f"safe_stop={result['safe_stop']}"
        )

        summary = summarize_run(GraphState(**result))
        metrics = compute_metrics([summary])
        latency = (
            f"{metrics.e2e_latency_seconds:.2f}s"
            if metrics.e2e_latency_seconds is not None
            else "n/a"
        )
        print(f"e2e_latency={latency}")
        print(f"Telemetry (JSONL): {telemetry_path}")
        print(f"Workspace: {workspace}")
