# Scenario: Brownfield — Fix a real concurrency bug

## What this demonstrates

An enhancement/bug-fix against **existing** code, with a **deliberate first-attempt
test failure that triggers a real bounded retry** — this is what makes the
reliability metrics (retry frequency, MTTR) non-vacuous rather than always reading
zero. It also demonstrates the codebase-impact-review gate and the merge/release
gate with a real git commit.

**Requirement given to the orchestrator:**
> The click-analytics counter under-counts on concurrent redirects; make it thread-/process-safe.

**Pre-existing condition:** the target app's `increment_click` starts out as a
read-modify-write against the ORM object — a genuine lost-update race under
concurrent access. A QA-authored regression test
(`orchestrator/scripts/scenario_seeds/brownfield_test_concurrency.py`, seeded into
the workspace as `tests/test_concurrency.py` before Coder ever runs) already exists
and is already failing when the fix request comes in — this is "make a failing test
pass," not "notice there might be a bug."

## Nodes and paths exercised

Codebase Reasoner (impact analysis) → **[gate: codebase_impact_review]** →
Architecture/Design → Decomposer/Planner → Coder → Test Executor — **first attempt
genuinely fails** the concurrency test → bounded retry (Coder re-invoked with the
failure fed back into its prompt) → Test Executor re-runs, **genuinely passes** →
Documentation → Release Readiness Gate → **[gate: merge_release_approval]** → real
`git commit`.

## Why this needs PostgreSQL, not SQLite

The rest of the test suite uses in-memory SQLite (fast, portable, fine for CRUD-level
tests). This scenario's regression test specifically does not: SQLite serializes
writes at the connection level and does not reproduce the same lost-update race a
real MVCC database exhibits under concurrent transactions. Testing a concurrency bug
against a database whose concurrency model differs from production would validate
nothing. The seed test has its own `pytest.mark.skipif` guard — if Postgres isn't
reachable it **skips**, it doesn't fail, so the rest of the suite stays honest.

## Run it

```bash
# Requires PostgreSQL reachable via POSTGRES_* env vars (docker-compose provides
# this automatically; for a standalone host run, point at any reachable instance).
POSTGRES_USER=orchestrator POSTGRES_PASSWORD=orchestrator POSTGRES_HOST=localhost \
POSTGRES_PORT=5432 POSTGRES_DB=orchestrator \
python orchestrator/scenarios/run_brownfield.py

python orchestrator/scenarios/run_brownfield.py --live    # real claude CLI + interactive gates
```

## What "validation" means for this run

Both attempts are **actually executed** against real PostgreSQL, not just replayed
as pre-recorded pass/fail flags. Attempt 1's code is genuinely broken and genuinely
fails; attempt 2's code is genuinely correct and genuinely passes. This was verified
independently three separate times during development: directly against a live
Postgres container with 50 concurrent threads (7/50 and then 6/50 increments
survived against the buggy code across two separate runs — a dramatic, reproducible
lost-update rate, not a flaky test), and again against a hand-written atomic fix
(50/50 survived), confirming the test is a valid discriminator before it was ever
used in this fixture.

## Actual captured run (replay mode, against a real local Postgres)

```
=== Running 'brownfield' scenario in replay mode ===
[13:28:09] requirement_clarifier    node_end           clarified requirement, 0 ambiguities surfaced | 0ms

--- GATE (replayed from fixture): codebase_impact_review -> approved ---
[13:28:10] codebase_reasoner        node_start         Scanned ... for keywords ['click', 'analytics',
  'counter', 'under', 'counts', 'concurrent']...: 10 module(s), 1 API file(s) impacted.
[13:28:10] codebase_reasoner        gate_decision      codebase_impact_review | decision=approved
[13:28:10] architecture_design      node_end           Change scoped to existing file(s): app/auth.py,
  app/db.py, app/models.py, app/rate_limit.py, app/repository.py, and 6 more. ...
[13:28:10] decomposer_planner       node_end           plan ready | 0ms
[13:28:10] coder                    node_end           attempt 1: generated 1 file(s) (replay mode) | 0ms
[13:28:13] test_executor            node_start         running pytest for attempt 1
[13:28:13] test_executor            retry              tests failed, retrying (attempt 2 of 4)
[13:28:13] test_executor            node_end           tests failed, retrying (attempt 2 of 4) | 3172ms
[13:28:13] coder                    node_end           attempt 2: generated 2 file(s) (replay mode) | 0ms
[13:28:16] test_executor            node_start         running pytest for attempt 2
[13:28:16] test_executor            node_end           tests passed | 3468ms

--- GATE (replayed from fixture): merge_release_approval -> approved ---
[13:28:16] release_gate             node_start         0 guardrail finding(s) before merge review
[13:28:17] release_gate             node_end           committed 24bffcf4 | 453ms

=== Run finished: run_status=completed ===
retry_count=1 rollback_count=0 safe_stop=False
e2e_latency=7.69s
```

## Notable: what Coder actually generated

**Attempt 1** (hand-authored per the plan's documented escape hatch — live
generation converged too well on the real fix immediately once a separate CLI
working-directory bug was fixed, so a realistic *first* attempt had to be
constructed deliberately): guards `increment_click` with `threading.Lock()`
instantiated fresh inside the method on every call. This looks like a fix and would
pass casual review, but each concurrent call gets its own independent `Lock`
object, providing zero actual mutual exclusion. Verified failing: 11/50 increments
survived.

**Attempt 2** (genuine live Claude Sonnet 5 output): a single atomic
`UPDATE short_urls SET click_count = click_count + 1 WHERE code = :code` statement
via SQLAlchemy's `update()` construct, with a well-reasoned docstring explaining
*why* an atomic UPDATE closes the race window a read-then-write can't, plus a note
about `synchronize_session="fetch"` for local session-identity-map correctness that
goes beyond what was asked.
