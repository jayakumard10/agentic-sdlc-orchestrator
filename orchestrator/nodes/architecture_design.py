"""Architecture/Design node: the *how* - component shape, API/schema design, data changes.

Deterministic heuristic reasoning over the clarified requirement and (when present)
the Codebase Reasoner's impact analysis - not an LLM call. Kept distinct from
Decomposer/Planner, which reasons about *what tasks, in what order*, not *how the
system should look*. No gate: this node isn't in the five-gate distribution, its
output flows straight into planning. Runs identically in live and replay mode -
only the Coder node's output is fixture-replayed.
"""

from __future__ import annotations

import time

from state import ArchitectureDesign, AuditEvent, GraphState


def architecture_design(state: GraphState) -> dict:
    start = time.monotonic()

    if state.codebase_impact.skipped:
        summary = (
            f"Greenfield: introduce new component(s) to satisfy "
            f"'{state.requirement_clarified}'. No existing modules to integrate against "
            "beyond the target app's existing FastAPI app instance and repository layer."
        )
        api_schema_changes = [f"New endpoint(s) to support: {state.requirement_clarified}"]
    elif state.codebase_impact.impacted_apis or state.codebase_impact.impacted_modules:
        touched = state.codebase_impact.impacted_modules + state.codebase_impact.impacted_apis
        summary = (
            f"Change scoped to existing file(s): {', '.join(touched)}. Modify in place to "
            f"satisfy '{state.requirement_clarified}' without changing public API signatures "
            "unless the impacted file is itself an API module."
        )
        api_schema_changes = [
            f"Review signature stability of: {api}" for api in state.codebase_impact.impacted_apis
        ]
    else:
        summary = (
            f"No impacted files were identified by the Codebase Reasoner for "
            f"'{state.requirement_clarified}'; treating as a net-new addition."
        )
        api_schema_changes = []

    design = ArchitectureDesign(summary=summary, api_schema_changes=api_schema_changes)

    events = [
        AuditEvent(node="architecture_design", event_type="node_start", detail="designing"),
        AuditEvent(
            node="architecture_design",
            event_type="node_end",
            detail=summary,
            latency_ms=(time.monotonic() - start) * 1000,
        ),
    ]

    return {"architecture_design": design, "events": events}
