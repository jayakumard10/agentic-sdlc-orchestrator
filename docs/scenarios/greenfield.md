# Scenario: Greenfield — Add a QR code endpoint

## What this demonstrates

A brand-new feature request against a service with no existing code related to it.
This is the "clean slate" path through the orchestrator: two human-approval gates
that only ever fire on greenfield runs (clarification and plan approval), and the
explicit conditional edge that skips Codebase Reasoner entirely — there is nothing
to do impact analysis on yet.

**Requirement given to the orchestrator:**
> Add a QR code generation endpoint for shortened URLs, returning a PNG the client can embed.

## Nodes and paths exercised

Requirement Clarifier → **[gate: clarification_approval]** → Architecture/Design
(Codebase Reasoner skipped — conditional edge in `graph.py`, since `scenario_type ==
"greenfield"`) → Decomposer/Planner → **[gate: plan_approval]** → Coder → Test
Executor ‖ Documentation (parallel fan-out/join) → Release Readiness Gate →
**[gate: merge_release_approval]** → real `git commit` in the target app's own
history.

## Run it

```bash
python orchestrator/scenarios/run_greenfield.py          # replay mode (default, no login needed)
python orchestrator/scenarios/run_greenfield.py --live    # real claude CLI + interactive gates
```

## What "validation" means for this run

- Coder's generated code (`app/qr.py`, plus wiring into `app/main.py`, plus a new
  `tests/test_qr.py`) is written into a real workspace and **actually executed** by
  Test Executor via a sandboxed `pytest` subprocess — not just trusted from the
  fixture.
- Release Gate's guardrail scan (unsafe calls / DDL changes / secret-shaped strings)
  runs against the real generated diff before the merge gate is even reachable.
- A real `git commit` lands in the target app's own nested repository on approval.

## Actual captured run (replay mode)

```
=== Running 'greenfield' scenario in replay mode ===
Workspace: C:\agentic-sdlc-orchestrator\.scenario_runs\greenfield

--- GATE (replayed from fixture): clarification_approval -> approved ---
[13:27:53] requirement_clarifier    node_start         parsing requirement (91 chars)
[13:27:53] requirement_clarifier    gate_decision      clarification_approval | decision=approved
[13:27:53] requirement_clarifier    node_end           clarified requirement, 0 ambiguities surfaced | 0ms
[13:27:53] architecture_design      node_start         designing
[13:27:53] architecture_design      node_end           Greenfield: introduce new component(s) to satisfy
  'Add a GET /{code}/qr endpoint that returns a PNG QR code encoding the short URL's
  redirect target, as a new app/qr.py module with no changes to existing endpoints.'.
  No existing modules to integrate against beyond the target app's existing FastAPI
  app instance and repository layer. | 0ms

--- GATE (replayed from fixture): plan_approval -> approved ---
[13:27:53] decomposer_planner       node_start         decomposed into 4 tasks
[13:27:53] decomposer_planner       gate_decision      plan_approval | decision=approved
[13:27:53] decomposer_planner       node_end           plan ready | 0ms
[13:27:53] coder                    node_end           attempt 1: generated 3 file(s) (replay mode) | 0ms
[13:27:53] documentation            node_start         generating target-app docs
[13:27:53] documentation            node_end           wrote 1 doc file(s) | 0ms
[13:27:56] test_executor            node_start         running pytest for attempt 1
[13:27:56] test_executor            node_end           tests passed | 2781ms

--- GATE (replayed from fixture): merge_release_approval -> approved ---
[13:27:56] release_gate             node_start         0 guardrail finding(s) before merge review
[13:27:56] release_gate             gate_decision      merge_release_approval | decision=approved
[13:27:56] release_gate             node_end           committed 466b923a | 422ms

=== Run finished: run_status=completed ===
retry_count=0 rollback_count=0 safe_stop=False
e2e_latency=3.23s
```

Confirmed independently by running `pytest` directly against the resulting
workspace (not just the graph's own claim): **20/20 tests pass** — the 11 baseline
tests, the 4 API-key auth tests, and 5 new tests Claude wrote for the QR endpoint,
including one confirming the new route correctly stays unauthenticated (matching
the existing redirect route's public-access pattern) — inferred by the model
without being told explicitly.

## Notable: what Coder actually generated

`app/qr.py` — a new `APIRouter` with `GET /{code}/qr`, returning a PNG rendered via
the `qrcode` package. `app/main.py` gained one import and one `include_router` call.
No existing endpoint's signature changed.
