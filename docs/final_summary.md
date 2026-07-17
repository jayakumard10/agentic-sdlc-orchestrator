# Final Engineering Summary

## What was built

A real LangGraph `StateGraph` orchestrating 9 nodes (Requirement Clarifier,
Codebase Reasoner, Architecture/Design, Decomposer/Planner, Coder, Test Executor,
Documentation, Release Readiness Gate, Re-planner) with conditional routing,
genuine parallel fan-out/join, bounded retry, fallback, rollback, safe-stop, five
distinct human-approval gates, dual JSON-lines/console telemetry, and computed
reliability metrics — driving a real LLM (the `claude` CLI) to generate,
test, document, and merge changes to a Python/FastAPI URL-shortener service. Three
required scenarios (greenfield, brownfield, ambiguous) are captured as real fixtures
from genuine live-Claude runs, each independently verified by actually re-running
`pytest` against the resulting code rather than trusting a recorded pass/fail flag.
Full Docker Compose deployment: `git clone && docker-compose up` runs all three
demos end-to-end with no login, no key, and no manual setup.

Rough numbers: 129 tests across two suites (102 orchestrator, 27 target app),
80.8%/97% coverage respectively, ~50 commits mapping the build's actual phases.

## Plan and rationale

See [architecture.md](architecture.md) for the full design. In short: only the
Coder node calls an LLM; every other node is deterministic heuristic logic,
which keeps eight of nine nodes trivially testable and means replay fidelity only
has to solve reproducing what the LLM did, not the whole graph. Human gates are
real `interrupt()` calls in both live and replay mode — replay resumes the same
interrupt with a recorded decision instead of a live one, so the code path is
identical either way, not a simulated bypass.

## Risks identified and how they were mitigated

| Risk | Mitigation |
|---|---|
| An LLM-generated fix could silently be wrong | Every Coder attempt is actually executed via a sandboxed `pytest` subprocess, not trusted from a recorded claim. Verified independently for all three captured fixtures by re-running the test suite directly against the resulting workspace. |
| A human could approve a dangerous change by accident | Guardrail violations (unsafe calls, DDL changes, secret-shaped strings) force the merge to `rejected` even if the raw decision says "approved," unless `override_guardrails` is explicitly set — defense in depth, not just recording what was said. |
| A retry loop could run forever | Hard-bounded at `retry_limit` (3), after which the system falls back to a reduced-scope prompt exactly once, then rolls back if that also fails. Verified end-to-end with a synthetic fixture that exhausts all four attempts. |
| Rollback could leave the workspace in a worse state than before | `git reset --hard` alone leaves untracked files on disk (exactly what an uncommitted Coder attempt is) — found via integration testing, fixed by adding `git clean -fd`, now covered by a dedicated regression test that writes an untracked file and confirms it's actually gone after rollback. |
| A concurrency bug fix could look correct without actually being tested against real concurrent behavior | The brownfield scenario's regression test runs against real PostgreSQL specifically, not the SQLite the rest of the suite uses — SQLite's write-serialization would not have reproduced the same lost-update race a real MVCC database exhibits. Verified directly: 7/50 and 6/50 increments survived against the buggy code across two separate runs (a dramatic, reproducible failure, not test flakiness); 50/50 against a hand-verified atomic fix. |
| Fixtures captured independently might not compose if replayed together | Found exactly this: running all three scenarios against one cumulative shared workspace broke the third scenario, because a later fixture's captured file silently overwrote an earlier fixture's unrelated addition. Fixed by giving each scenario its own isolated workspace by default. |
| The confidentiality boundary on the assignment brief could leak into the public repo | The candidate's planning notes (`PLANNING.md`, containing the full Pass 1 plan and a running deviation log) live in this same working directory but are gitignored and were never committed at any point in this repo's history — confirmed via `git log`/`git status` throughout the build, not just at the end. |

## Validation approach

- **Unit and integration tests** for the orchestrator's own logic
  (`orchestrator/tests/`), including end-to-end tests of the real compiled graph
  covering every governance path: happy path, deliberate-failure-then-retry,
  re-planning, safe-stop, guardrail-forced rollback (both with and without a prior
  commit to revert to), and full retry-exhaustion-into-fallback-into-rollback.
- **Unit and integration tests** for the target app (`target_app/tests/`),
  covering the API surface, auth enforcement, rate limiting, and the repository
  layer.
- **Real, not mocked, verification of generated code.** Every captured fixture's
  code was independently confirmed to pass its test suite by actually running
  `pytest` against the resulting workspace — this is stated explicitly in each
  scenario walkthrough rather than assumed.
- **A real Docker Compose run**, twice: once with each service individually
  (`postgres` + `target_app`, confirmed via `curl` against the real running
  service), and once as the full `docker-compose up --build` a reviewer would
  actually run, confirming all three scenarios complete and the orchestrator
  container exits 0.
- **Metrics validated against hand-calculated values** across synthetic runs
  before being trusted on real ones (`test_telemetry_metrics.py`).

## Assumptions

- The "core APIs, analytics, reliability features" scope for the target app was
  interpreted as: `POST /shorten`, `GET /{code}` (redirect + click tracking),
  `GET /{code}/stats` (analytics), and rate limiting (the reliability feature).
- The ambiguous scenario's re-planning conflict is deterministic/scripted (a file
  named `*rate_limit*.py` already existing in the workspace) rather than something
  an LLM has to notice organically, prioritizing replay reproducibility over a more
  "realistic" but non-reproducible emergent discovery.
- A reviewer running the default `docker-compose up` path has no `claude` CLI
  authentication and isn't expected to need one — replay mode is the fully-
  supported default, not a degraded fallback.

## Known limitations (would address for production)

- **No database migration tooling.** `Base.metadata.create_all()` on startup
  instead of Alembic. Real production practice would use proper migrations;
  documented rather than hidden.
- **Lightweight API-key auth, not full user accounts.** A single shared-secret
  header guards `POST /shorten` and `GET /{code}/stats` (the two concrete abuse
  vectors in scope — anonymous link creation and reading another link's
  analytics); `GET /{code}` stays public by design, since that's the actual
  recipient-facing flow a URL shortener exists for. Full user auth (accounts,
  ownership, audit trail per user) would be the next step for a real production
  deployment, but was judged disproportionate to the time budget and to what's
  being evaluated here relative to orchestration depth.
- **Fallback, rollback, and safe-stop are real, tested infrastructure but not
  exercised by any of the three required demo scenarios.** By design — the
  brownfield scenario recovers within its bounded retry limit, so fallback/
  rollback are never reached in that demo. They're exercised directly by
  `orchestrator/tests/test_graph_integration.py` (`test_fallback_exhaustion_rolls_back`,
  both rollback tests, and `test_safe_stop_on_missing_fixture_never_reaches_release_gate`)
  through synthetic fixtures, which keeps each of the three named demos focused on
  the one gate/path it's meant to showcase rather than needing to contrive all six
  governance paths into three runs.
- **The demo scripts and fixture-capture tool are deliberately excluded from the
  orchestrator's own coverage report.** They're thin I/O wrappers around
  already-100%-covered graph logic; validated by actually running them rather than
  mocked, since a mock of `input()`/`print()`/file I/O would mostly test the mocks.
- **Codebase Reasoner's impact analysis is a keyword scan, not real static
  analysis.** Deliberately lightweight — it answers "what looks relevant", while
  actual code understanding is the LLM-powered Coder node's job. This is
  explicit in the node's own docstring, not an unstated shortcut, and it can
  over-match (a docstring mentioning "click analytics" coincidentally flagged
  `app/auth.py` as impacted during development) — bounded by capping how many
  files get spelled out in the downstream prompt rather than by chasing perfect
  precision.
- **The rate limiter is in-process, not distributed.** No Redis, no shared state
  across instances — appropriate for a single-container demo with no
  multi-instance concurrency to coordinate across, explicitly not appropriate for
  a horizontally-scaled production deployment.
- **No CI/CD pipeline.** Out of scope for the time budget; the test suites and
  coverage reports are the artifact a CI pipeline would run, not a CI
  configuration itself.

## What surprised me during the build

The single most informative failure was the ambiguous scenario's first fixture
capture attempt: it burned all four Coder attempts and safe-stopped, and the root
cause wasn't a flaky model or bad luck — it was that the re-planning mechanism's
whole point (giving Coder a more specific, reconciled instruction) never actually
reached Coder's prompt at all. The orchestrator-level state was being updated
correctly; the LLM-facing prompt just never included it. That's exactly the kind
of gap that's invisible until you actually run the thing end-to-end with a real
model in the loop — no amount of mocking would have surfaced it, which is the
strongest argument I have for why the "attempt live generation first, always"
discipline mattered throughout this build rather than being a box to check once.
