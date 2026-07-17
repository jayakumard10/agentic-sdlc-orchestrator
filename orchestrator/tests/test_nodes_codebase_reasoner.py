"""Tests for the Codebase Reasoner node: keyword-based impact scanning, the

brownfield-only codebase_impact_review gate, and the deterministic re-planning
conflict check used by the ambiguous scenario.
"""

from __future__ import annotations

from functools import partial
from pathlib import Path

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from checkpointer import build_memory_checkpointer
from nodes.codebase_reasoner import _detect_replanning_conflict, codebase_reasoner
from state import GraphState


def _seed_files(tmp_path: Path) -> None:
    app = tmp_path / "app"
    app.mkdir()
    (app / "analytics.py").write_text(
        "counter = 0\ndef increment_click_counter():\n    global counter\n    counter += 1\n",
        encoding="utf-8",
    )
    (app / "main.py").write_text(
        'from fastapi import FastAPI\napp = FastAPI()\n\n@app.get("/{code}")\n'
        "def redirect(code: str):\n    increment_click_counter()\n    return {}\n",
        encoding="utf-8",
    )
    (app / "unrelated.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")


def _build_graph(workspace: Path):
    graph = StateGraph(GraphState)
    graph.add_node("codebase_reasoner", partial(codebase_reasoner, workspace=workspace))
    graph.add_edge(START, "codebase_reasoner")
    graph.add_edge("codebase_reasoner", END)
    return graph.compile(checkpointer=build_memory_checkpointer())


def test_scan_classifies_modules_vs_apis_using_posix_paths(tmp_path: Path):
    """Regression test: Path.relative_to(...) stringifies with backslashes on

    Windows, which would corrupt matching once fixtures replay inside Linux
    containers. Found via smoke-testing during Phase 2.
    """
    _seed_files(tmp_path)
    compiled = _build_graph(tmp_path)
    config = {"configurable": {"thread_id": "cr-scan"}}

    result = compiled.invoke(
        GraphState(
            scenario_type="brownfield",
            requirement_raw="race condition",
            requirement_clarified="fix the race condition in the click counter for concurrent redirects",
        ),
        config=config,
    )
    payload = result["__interrupt__"][0].value
    assert payload["impacted_modules"] == ["app/analytics.py"]
    assert payload["impacted_apis"] == ["app/main.py"]
    assert "app/unrelated.py" not in payload["impacted_modules"]


def test_brownfield_gates_on_codebase_impact_review(tmp_path: Path):
    _seed_files(tmp_path)
    compiled = _build_graph(tmp_path)
    config = {"configurable": {"thread_id": "cr-brownfield"}}

    compiled.invoke(
        GraphState(
            scenario_type="brownfield",
            requirement_raw="x",
            requirement_clarified="fix the click counter",
        ),
        config=config,
    )
    resumed = compiled.invoke(
        Command(resume={"status": "approved", "decided_by": "human"}), config=config
    )
    assert resumed["gates"]["codebase_impact_review"].status == "approved"
    assert resumed["codebase_impact"].skipped is False


def test_ambiguous_runs_analysis_without_gating(tmp_path: Path):
    _seed_files(tmp_path)
    compiled = _build_graph(tmp_path)
    config = {"configurable": {"thread_id": "cr-ambiguous"}}

    result = compiled.invoke(
        GraphState(
            scenario_type="ambiguous",
            requirement_raw="x",
            requirement_clarified="improve reliability of the redirect and click counter path",
        ),
        config=config,
    )
    assert "__interrupt__" not in result
    assert result["gates"] == {}
    assert result["codebase_impact"].impacted_modules == ["app/analytics.py"]


def test_detect_replanning_conflict_finds_rate_limit_file(tmp_path: Path):
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "rate_limit.py").write_text(
        "def is_allowed(key): return True\n", encoding="utf-8"
    )
    reason = _detect_replanning_conflict(tmp_path)
    assert reason is not None
    assert "rate_limit.py" in reason


def test_detect_replanning_conflict_none_when_absent(tmp_path: Path):
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text("x = 1\n", encoding="utf-8")
    assert _detect_replanning_conflict(tmp_path) is None


def test_ambiguous_scenario_sets_replanning_triggered_when_conflict_found(tmp_path: Path):
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "rate_limit.py").write_text("x = 1\n", encoding="utf-8")
    compiled = _build_graph(tmp_path)
    config = {"configurable": {"thread_id": "cr-conflict"}}

    result = compiled.invoke(
        GraphState(
            scenario_type="ambiguous",
            requirement_raw="x",
            requirement_clarified="make the service more reliable",
        ),
        config=config,
    )
    assert result["replanning_triggered"] is True
    assert "rate_limit.py" in result["replanning_reason"]


def test_greenfield_impact_defaults_stay_untouched_when_node_not_invoked():
    """Greenfield skips this node entirely via a graph-level conditional edge

    (tested in test_graph_integration.py) - this just confirms the default state
    shape a skipped run would carry forward.
    """
    state = GraphState(scenario_type="greenfield", requirement_raw="x")
    assert state.codebase_impact.skipped is True
