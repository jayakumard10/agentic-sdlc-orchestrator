# Scenario: Ambiguous — Mid-flight re-planning

## What this demonstrates

A vague requirement that requires interpretation, plus a **deterministic, scripted**
mid-flight conflict discovery that triggers dynamic re-planning — a real,
observable change in the task list, not a relabeled no-op.

**Requirement given to the orchestrator:**
> Make the service more reliable.

This is deliberately underspecified: it could mean rate limiting, retries, caching,
circuit breakers, better error handling, or something else entirely. Requirement
Clarifier flags it as ambiguous (vague-qualifier detection on "reliable" and "more").

## Why the conflict trigger is scripted, not emergent

An earlier design decision (documented in the planning notes) chose a
**deterministic** conflict trigger over relying on an LLM to notice a collision on
its own: Codebase Reasoner checks whether the workspace already contains a file
matching `*rate_limit*.py` — which it does, since the target app already has
`app/rate_limit.py`. This keeps replay reproducible: the same fixture produces the
same conflict, every time, regardless of which model runs it or how it happens to
be feeling that day.

## Nodes and paths exercised

Requirement Clarifier (ambiguity surfaced, no gate — clarification approval is
greenfield-only) → Codebase Reasoner (conflict detected: existing rate-limiting
middleware) → Architecture/Design → Decomposer/Planner (**initial** 4-task plan) →
Re-planner → **[gate: replanning_approval]** → Decomposer/Planner (**revised**
5-task plan, with a new T0 reconciliation task prepended) → Coder → Test Executor ‖
Documentation → Release Readiness Gate → **[gate: merge_release_approval]**.

## Run it

```bash
python orchestrator/scenarios/run_ambiguous.py          # replay mode
python orchestrator/scenarios/run_ambiguous.py --live    # real claude CLI + interactive gates
```

## What "validation" means for this run

The task list genuinely differs before and after the re-planning gate — this is
checked directly in the console trace (`4 tasks` → `5 tasks (revised plan)`), not
just asserted. Coder's prompt includes the revised task list (a fix made during
development after the first live capture attempt burned all 4 retry attempts on a
broken cross-file-consistency bug traced to this exact gap — see the brownfield/
commit history for details), so the re-planning mechanism has a real, verifiable
effect on what gets generated, not just on orchestrator bookkeeping.

## Actual captured run (replay mode)

```
=== Running 'ambiguous' scenario in replay mode ===
[13:28:28] requirement_clarifier    node_end           clarified requirement, 2 ambiguities surfaced | 0ms
[13:28:28] codebase_reasoner        node_start         Scanned ... for keywords ['service', 'reliable']:
  0 module(s), 0 API file(s) impacted.
[13:28:28] codebase_reasoner        node_end           impact analysis complete; re-planning conflict
  detected: Existing rate-limiting middleware found at 'app/rate_limit.py'; the
  planned interpretation of this requirement risks duplicating it rather than
  reusing it. | 31ms
[13:28:28] decomposer_planner       node_start         decomposed into 4 tasks
[13:28:28] decomposer_planner       node_end           plan ready | 0ms

--- GATE (replayed from fixture): replanning_approval -> approved ---
[13:28:29] replanner                node_start         surfacing re-planning conflict: Existing
  rate-limiting middleware found at 'app/rate_limit.py'; ...
[13:28:29] replanner                gate_decision      replanning_approval | decision=approved
[13:28:29] replanner                node_end           handing back to decomposer_planner for a revised plan
[13:28:29] decomposer_planner       node_start         decomposed into 5 tasks (revised plan)
[13:28:29] decomposer_planner       node_end           plan ready | 0ms
[13:28:29] coder                    node_end           attempt 1: generated 5 file(s) (replay mode) | 15ms
[13:28:31] test_executor            node_start         running pytest for attempt 1
[13:28:31] test_executor            node_end           tests passed | 2625ms

--- GATE (replayed from fixture): merge_release_approval -> approved ---
[13:28:32] release_gate             node_end           committed 9351c7f9 | 437ms

=== Run finished: run_status=completed ===
retry_count=0 rollback_count=0 safe_stop=False
e2e_latency=3.94s
```

Confirmed independently: **24/24 tests pass** against the resulting workspace — the
11 baseline tests, 4 auth tests, 2 pre-existing repository tests, plus 7 new tests
Claude wrote for the reliability changes.

## Notable: what Coder actually generated

Claude's interpretation of "more reliable" went a different direction than the
scripted rate-limiting conflict anticipated: **database-connection resilience** —
`GET /health` now reports a degraded status when the database is unreachable rather
than throwing an unhandled exception, unexpected errors return a generic 500
instead of leaking internals, and the SQLAlchemy engine gained `pool_pre_ping` plus
a bounded connect timeout for both the SQLite and PostgreSQL code paths. This is a
reasonable, well-scoped engineering judgment call — nothing existing broke, nothing
was duplicated — and the re-planning mechanism itself demonstrated correctly
regardless of which direction the model ultimately chose: the gate fired, the plan
was genuinely revised, and Coder worked from that revised context rather than a
generic instruction with no scope guidance.
