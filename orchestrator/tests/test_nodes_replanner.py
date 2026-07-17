"""Tests for the Re-planner node: the replanning_approval gate and the full

conflict-detection -> gate -> revised-plan chain across Codebase Reasoner,
Re-planner, and Decomposer/Planner together.
"""

from __future__ import annotations

from functools import partial
from pathlib import Path

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from checkpointer import build_memory_checkpointer
from nodes.codebase_reasoner import codebase_reasoner
from nodes.decomposer_planner import decomposer_planner
from nodes.replanner import replanner
from state import GraphState, Task


def test_replanner_gates_and_records_decision():
    graph = StateGraph(GraphState)
    graph.add_node("replanner", replanner)
    graph.add_edge(START, "replanner")
    graph.add_edge("replanner", END)
    compiled = graph.compile(checkpointer=build_memory_checkpointer())

    config = {"configurable": {"thread_id": "rp-basic"}}
    result = compiled.invoke(
        GraphState(
            scenario_type="ambiguous",
            requirement_raw="x",
            replanning_reason="conflict with existing middleware",
            tasks=[Task(id="T1", description="Implement", depends_on=[])],
        ),
        config=config,
    )
    payload = result["__interrupt__"][0].value
    assert payload["gate_type"] == "replanning_approval"
    assert payload["reason"] == "conflict with existing middleware"
    assert [t["id"] for t in payload["initial_tasks"]] == ["T1"]

    resumed = compiled.invoke(
        Command(resume={"status": "approved", "decided_by": "human"}), config=config
    )
    assert resumed["gates"]["replanning_approval"].status == "approved"


def test_full_conflict_to_revised_plan_chain(tmp_path: Path):
    """End-to-end chain: Codebase Reasoner detects the conflict, Decomposer/Planner

    builds the initial plan, Re-planner gates, and the second Decomposer/Planner
    pass produces a genuinely different (revised) plan.
    """
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "rate_limit.py").write_text(
        "def is_allowed(key): return True\n", encoding="utf-8"
    )

    graph = StateGraph(GraphState)
    graph.add_node("codebase_reasoner", partial(codebase_reasoner, workspace=tmp_path))
    graph.add_node("decomposer_planner", decomposer_planner)
    graph.add_node("replanner", replanner)
    graph.add_edge(START, "codebase_reasoner")
    graph.add_edge("codebase_reasoner", "decomposer_planner")
    graph.add_edge("decomposer_planner", "replanner")
    graph.add_edge("replanner", END)
    compiled = graph.compile(checkpointer=build_memory_checkpointer())

    config = {"configurable": {"thread_id": "rp-chain"}}
    compiled.invoke(
        GraphState(
            scenario_type="ambiguous",
            requirement_raw="x",
            requirement_clarified="make the service more reliable by adding rate limiting",
        ),
        config=config,
    )
    resumed = compiled.invoke(
        Command(resume={"status": "approved", "decided_by": "human"}), config=config
    )
    assert resumed["replanning_triggered"] is True

    # simulate the graph's real loop-back: call decomposer_planner again with the
    # post-replanner state, exactly as graph.py's routing does
    revised = decomposer_planner(GraphState(**resumed))
    assert [task.id for task in revised["tasks"]] == ["T0", "T1", "T2", "T3", "T4"]
