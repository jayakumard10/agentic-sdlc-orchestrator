"""Coder node: generates target-app code, live via the `claude` CLI or replayed from a fixture.

The only node in the graph that calls an LLM. Live mode shells out to the standalone
`claude` CLI (authenticated via the operator's Claude Pro subscription login - no API
key anywhere in this system) and parses its `--output-format json` response. Replay
mode reads a previously captured fixture instead, so the default `docker-compose up`
path needs no login at all. Both paths converge on the same output shape
(`CoderOutput`), so downstream nodes never need to know which one ran.
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

import tools
from state import AuditEvent, CoderOutput, GraphState

CLAUDE_MODEL = "claude-sonnet-5"
CLAUDE_CLI_TIMEOUT_SECONDS = 300


class FixtureNotFoundError(RuntimeError):
    """Raised in replay mode when no recorded fixture matches the current run."""


def _build_prompt(state: GraphState) -> str:
    if state.fallback_triggered:
        lines = [
            "You are generating production-quality Python/FastAPI code for a URL "
            "shortener service.",
            f"Previous attempts to satisfy this requirement failed after "
            f"{state.retry_limit} retries: {state.requirement_clarified}",
            "Fall back to the SIMPLEST possible correct implementation - prefer a "
            "minimal, obviously-correct approach over an elegant one.",
        ]
    else:
        lines = [
            "You are generating production-quality Python/FastAPI code for a URL "
            "shortener service.",
            f"Requirement: {state.requirement_clarified}",
            f"Architecture notes: {state.architecture_design.summary}",
        ]
        if state.test.failures:
            lines.append("The previous attempt failed these tests - fix the root cause:")
            lines.extend(f"- {failure}" for failure in state.test.failures)
    lines.append(
        "Return ONLY a JSON object mapping relative file paths to full file contents, "
        "no prose, no markdown fences, no explanation outside the JSON."
    )
    return "\n".join(lines)


def _invoke_claude_cli(prompt: str) -> dict[str, str]:
    proc = subprocess.run(
        ["claude", "-p", prompt, "--model", CLAUDE_MODEL, "--output-format", "json"],
        capture_output=True,
        text=True,
        timeout=CLAUDE_CLI_TIMEOUT_SECONDS,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"claude CLI exited {proc.returncode}: {proc.stderr.strip()}")
    payload = json.loads(proc.stdout)
    if payload.get("is_error") or payload.get("subtype") != "success":
        raise RuntimeError(f"claude CLI reported an error: {payload}")
    code_files = json.loads(payload["result"])
    if not isinstance(code_files, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in code_files.items()
    ):
        raise ValueError("claude CLI result did not decode to a flat {path: content} object")
    return code_files


def _load_fixture(fixtures_dir: Path, scenario_type: str) -> dict:
    fixture_path = fixtures_dir / scenario_type / "transcript.json"
    if not fixture_path.is_file():
        raise FixtureNotFoundError(
            "live generation requires an authenticated `claude` CLI (--live mode); "
            f"this input has no recorded fixture for scenario '{scenario_type}' "
            f"(expected {fixture_path})"
        )
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def _select_fixture_attempt(
    attempts: list[dict], attempt_number: int, fallback_triggered: bool
) -> dict:
    if fallback_triggered:
        fallback_entries = [entry for entry in attempts if entry.get("fallback")]
        if fallback_entries:
            return fallback_entries[0]
        raise FixtureNotFoundError(
            "fallback path was triggered but this scenario's fixture has no recorded "
            "fallback attempt"
        )
    matching = [entry for entry in attempts if entry["attempt_number"] == attempt_number]
    if matching:
        return matching[0]
    raise FixtureNotFoundError(
        f"no recorded fixture attempt #{attempt_number} for this scenario "
        f"(fixture has {len(attempts)} attempt(s))"
    )


_FIXTURE_FAILURE_TYPES = (
    FixtureNotFoundError,
    RuntimeError,
    ValueError,
    json.JSONDecodeError,
    subprocess.TimeoutExpired,
    KeyError,
    OSError,
)


def coder(state: GraphState, workspace: Path, fixtures_dir: Path) -> dict:
    start = time.monotonic()
    attempt_number = state.retry_count + 1

    try:
        if state.mode == "live":
            code_files = _invoke_claude_cli(_build_prompt(state))
            fixture_source = None
            rationale = f"Live generation, attempt {attempt_number}."
        else:
            fixture = _load_fixture(fixtures_dir, state.scenario_type)
            entry = _select_fixture_attempt(
                fixture.get("attempts", []), attempt_number, state.fallback_triggered
            )
            code_files = entry["code_files"]
            fixture_source = str(fixtures_dir / state.scenario_type / "transcript.json")
            rationale = entry.get("rationale", "")
    except _FIXTURE_FAILURE_TYPES as exc:
        return {
            "safe_stop": True,
            "run_status": "failed",
            "coder": CoderOutput(attempt_number=attempt_number, rationale=str(exc)),
            "events": [AuditEvent(node="coder", event_type="safe_stop", detail=str(exc))],
        }

    commit_sha_before = tools.git_current_commit(workspace)
    tools.write_code_files(workspace, code_files)

    coder_output = CoderOutput(
        code_files=code_files,
        attempt_number=attempt_number,
        fixture_source=fixture_source,
        commit_sha_before=commit_sha_before,
        rationale=rationale,
    )

    events = [
        AuditEvent(
            node="coder",
            event_type="node_end",
            detail=(
                f"attempt {attempt_number}: generated {len(code_files)} file(s) "
                f"({state.mode} mode)"
            ),
            latency_ms=(time.monotonic() - start) * 1000,
        )
    ]

    return {"coder": coder_output, "events": events}
