"""Tests for GraphState: reducers, defaults, and the checkpoint-serde allowlist

used to persist its nested Pydantic submodels.
"""

from __future__ import annotations

import os

import pytest
from langgraph.graph import END, START, StateGraph
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError

from checkpointer import (
    _discover_state_model_allowlist,
    _postgres_conn_string,
    build_memory_checkpointer,
    build_postgres_checkpointer,
)
from state import AuditEvent, CoderOutput, GraphState, RunMetrics


def _postgres_reachable() -> bool:
    if not os.environ.get("POSTGRES_USER"):
        return False
    try:
        url = _postgres_conn_string().replace("postgresql://", "postgresql+psycopg://", 1)
        connection = create_engine(url).connect()
        connection.close()
        return True
    except OperationalError:
        return False


def test_graph_state_requires_scenario_type():
    state = GraphState(scenario_type="brownfield", requirement_raw="x")
    assert state.scenario_type == "brownfield"
    assert state.mode == "replay"
    assert state.run_status == "running"
    assert state.retry_count == 0
    assert state.retry_limit == 3
    assert state.events == []
    assert state.coder_attempts == []
    assert state.finished_at is None


def test_events_field_uses_additive_reducer_under_parallel_writes():
    """The Test Executor / Documentation parallel fan-out both append to events -

    confirm LangGraph actually merges concurrent writes via operator.add rather than
    one branch's update silently clobbering the other's.
    """

    def branch_a(state: GraphState) -> dict:
        return {"events": [AuditEvent(node="a", event_type="node_start", detail="a")]}

    def branch_b(state: GraphState) -> dict:
        return {"events": [AuditEvent(node="b", event_type="node_start", detail="b")]}

    graph = StateGraph(GraphState)
    graph.add_node("a", branch_a)
    graph.add_node("b", branch_b)
    graph.add_edge(START, "a")
    graph.add_edge(START, "b")
    graph.add_edge("a", END)
    graph.add_edge("b", END)
    compiled = graph.compile()

    result = compiled.invoke(GraphState(scenario_type="greenfield", requirement_raw="x"))

    assert len(result["events"]) == 2
    assert {event.node for event in result["events"]} == {"a", "b"}


def test_coder_attempts_field_uses_additive_reducer():
    """Same pattern, different field: every Coder invocation across a retry loop

    must stay visible in coder_attempts, not just the latest one.
    """

    def first_attempt(state: GraphState) -> dict:
        output = CoderOutput(attempt_number=1, rationale="first")
        return {"coder": output, "coder_attempts": [output]}

    def second_attempt(state: GraphState) -> dict:
        output = CoderOutput(attempt_number=2, rationale="second")
        return {"coder": output, "coder_attempts": [output]}

    graph = StateGraph(GraphState)
    graph.add_node("first", first_attempt)
    graph.add_node("second", second_attempt)
    graph.add_edge(START, "first")
    graph.add_edge("first", "second")
    graph.add_edge("second", END)
    compiled = graph.compile()

    result = compiled.invoke(GraphState(scenario_type="brownfield", requirement_raw="x"))

    assert len(result["coder_attempts"]) == 2
    assert [attempt.attempt_number for attempt in result["coder_attempts"]] == [1, 2]
    assert result["coder"].attempt_number == 2


def test_checkpointer_serde_allowlist_discovers_every_state_submodel():
    allowlist = _discover_state_model_allowlist()
    names = {name for _, name in allowlist}
    assert {
        "GraphState",
        "AuditEvent",
        "GateRecord",
        "CodebaseImpact",
        "ArchitectureDesign",
        "Task",
        "CoderOutput",
        "TestResult",
        "GuardrailViolation",
        "DocumentationOutput",
        "RunMetrics",
    } <= names


def test_memory_checkpointer_round_trips_nested_submodels():
    """Regression test for the deprecation warning found during Phase 2: without

    the allowlist, LangGraph's default serde falls back to a path it warns will be
    blocked in a future version for any custom Pydantic type nested in state. This
    confirms the actual round-trip still works with the configured serde in place.
    """
    graph = StateGraph(GraphState)
    graph.add_node("noop", lambda state: {})
    graph.add_edge(START, "noop")
    graph.add_edge("noop", END)
    compiled = graph.compile(checkpointer=build_memory_checkpointer())

    config = {"configurable": {"thread_id": "state-roundtrip-test"}}
    result = compiled.invoke(
        GraphState(
            scenario_type="ambiguous",
            requirement_raw="x",
            metrics=RunMetrics(success_rate=1.0),
        ),
        config=config,
    )
    assert result["metrics"].success_rate == 1.0


@pytest.mark.skipif(
    not _postgres_reachable(), reason="requires PostgreSQL reachable via POSTGRES_* env vars"
)
def test_postgres_checkpointer_round_trips_and_survives_a_fresh_connection():
    """The whole reason PostgresSaver was chosen over MemorySaver: a pending gate

    must survive something equivalent to a container restart. Simulates that by
    entering a *second*, independent build_postgres_checkpointer() context and
    confirming it can resume a thread a prior context paused.
    """
    graph = StateGraph(GraphState)
    graph.add_node("noop", lambda state: {"requirement_clarified": "seen"})
    graph.add_edge(START, "noop")
    graph.add_edge("noop", END)

    config = {"configurable": {"thread_id": "postgres-durability-test"}}

    with build_postgres_checkpointer() as checkpointer:
        compiled = graph.compile(checkpointer=checkpointer)
        compiled.invoke(GraphState(scenario_type="brownfield", requirement_raw="x"), config=config)

    # fresh checkpointer instance/connection - simulates resuming after a restart
    with build_postgres_checkpointer() as checkpointer2:
        compiled2 = graph.compile(checkpointer=checkpointer2)
        state = compiled2.get_state(config)
        assert state.values["requirement_clarified"] == "seen"
