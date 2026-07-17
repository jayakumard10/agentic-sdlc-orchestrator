# Agentic SDLC Orchestrator

**A requirement goes in. A reviewed, tested, merged change comes out — with a human
approving every high-impact step along the way.**

A working prototype built on a real [LangGraph](https://github.com/langchain-ai/langgraph)
`StateGraph`: 9 orchestration nodes, 5 human-approval gates, bounded retry →
fallback → rollback → safe-stop governance, genuine parallel execution, dynamic
re-planning, and a full JSON-lines audit trail — driving a real LLM (`claude`) to
generate, test, document, and merge changes to a live FastAPI service.

The primary deliverable is **the orchestrator itself**. The system it builds/evolves
— a small URL-shortener service — is the demo substrate that proves it actually
works, not the point of the exercise.

![Demo: shortening a real URL and reading back the redirect + analytics](docs/demo.gif)

## Example output (real, captured from an actual run)

The brownfield scenario end-to-end — a genuine first-attempt test failure, a real
bounded retry, and a real recovery, replayed deterministically against actual
PostgreSQL:

```
=== Running 'brownfield' scenario in replay mode ===
Workspace: /tmp/scenario_runs/brownfield

--- GATE (replayed from fixture): codebase_impact_review -> approved ---
[14:12:24] codebase_reasoner        node_start         Scanned ... for keywords ['click',
  'analytics', 'counter', 'under', 'counts', 'concurrent']...: 9 module(s), 1 API file(s) impacted.
[14:12:24] architecture_design      node_end           Change scoped to existing file(s):
  app/auth.py, app/db.py, app/models.py, app/rate_limit.py, app/repository.py, and 5 more. ...
[14:12:24] decomposer_planner       node_end           plan ready | 0ms
[14:12:24] coder                    node_end           attempt 1: generated 1 file(s) (replay mode)
[14:12:26] test_executor            node_start         running pytest for attempt 1
[14:12:26] test_executor            retry              tests failed, retrying (attempt 2 of 4)
[14:12:27] coder                    node_end           attempt 2: generated 2 file(s) (replay mode)
[14:12:28] test_executor            node_start         running pytest for attempt 2
[14:12:28] test_executor            node_end           tests passed | 2143ms

--- GATE (replayed from fixture): merge_release_approval -> approved ---
[14:12:28] release_gate             node_end           committed 34d6529a | 45ms

=== Run finished: run_status=completed ===
retry_count=1 rollback_count=0 safe_stop=False
e2e_latency=2.27s
```

Full, unabridged traces for all three scenarios (including the ambiguous
scenario's task list visibly changing from 4 tasks to "5 tasks (revised plan)" at
its re-planning gate) are in [docs/scenarios/](docs/scenarios/) — every one
annotated with what it demonstrates and why, not just pasted output.

### Re-recording the demo GIF

The recording above shows [`scripts/demo_shorten_url.ps1`](scripts/demo_shorten_url.ps1)
in action — a real long URL shortened, redirected, and its click count read back.
To update it (e.g. after a change to the target app):

1. **[ScreenToGif](https://www.screentogif.com/)** (Windows, free, ~5MB, captures
   directly to GIF) — or `Cmd+Shift+5` (macOS built-in) / [Peek](https://github.com/phw/peek)
   (Linux).
2. Bring up the stack (`docker compose up -d postgres target_app`), terminal sized
   to something reasonable (~100×30).
3. Start recording, run the script, stop a couple seconds after the analytics
   line prints.
4. Overwrite `docs/demo.gif`.

For an orchestration-focused recording instead (or in addition), record
`docker compose up --build` and stop at `=== All scenarios complete ===` (~15–20s).

## Quickstart (30 seconds, nothing to configure)

```bash
git clone <this-repo>
cd agentic-sdlc-orchestrator
cp .env.example .env      # PowerShell: copy .env.example .env
docker compose up --build
```

No login, no API key, nothing to configure. (If you have `make` installed, `make up`
is equivalent and shorter — see [`make help`](Makefile) for other shortcuts. Not
required either way.)

This brings up:

- **postgres** — the checkpointer's durability layer and the target app's database
- **target_app** — the URL shortener, live at `http://localhost:8000`
- **orchestrator** — runs all three required scenarios (greenfield, brownfield,
  ambiguous) in sequence against the real compiled graph, replaying the recorded
  fixtures deterministically, then exits 0. Watch its output in the same terminal,
  or `docker compose logs orchestrator` after the fact.

Each scenario's gates are answered from the actual human decisions recorded when
that scenario's fixture was captured — the same `interrupt()`/resume code path
runs whether the answer came from a keyboard or a file (see
[docs/architecture.md](docs/architecture.md)).

After the run, `postgres` and `target_app` keep running:

```bash
curl http://localhost:8000/health
```

If `make` is installed, `make help` lists every shortcut (individual scenarios,
test suites, coverage regeneration, teardown) — see the [Makefile](Makefile) for
the equivalent raw commands either way.

## Try the actual product: shorten a real URL

Beyond the orchestration demos, `target_app` is a real, running URL shortener.
This shortens an actual URL, then follows the redirect and reads back the click
analytics — one command, real output:

```powershell
# PowerShell
.\scripts\demo_shorten_url.ps1
```

```bash
# bash / Git Bash / macOS / Linux
./scripts/demo_shorten_url.sh
# or: make demo-shorten-url
```

```
==================================================================
 URL Shortener - live demo against http://localhost:8000
==================================================================

Original URL:
  https://www.schwab.com/invest-with-us

Shortened URL:
  http://localhost:8000/ZbBFho3

==================================================================
 Following the redirect
==================================================================

  location: https://www.schwab.com/invest-with-us

==================================================================
 Analytics (click count after one redirect)
==================================================================

{"code":"ZbBFho3","long_url":"https://www.schwab.com/invest-with-us","click_count":1,...}
```

Pass any URL as an argument (`./scripts/demo_shorten_url.sh https://example.com`) —
`postgres` + `target_app` need to already be running (`docker compose up` or
`docker compose up -d postgres target_app`).

## Running one scenario at a time

```bash
docker compose run --rm orchestrator python scenarios/run_greenfield.py
docker compose run --rm orchestrator python scenarios/run_brownfield.py
docker compose run --rm orchestrator python scenarios/run_ambiguous.py

# with make installed, these are equivalent:
make demo-greenfield
```

Each scenario has a companion write-up with an actual captured run and an
explanation of what it demonstrates:

- [docs/scenarios/greenfield.md](docs/scenarios/greenfield.md) — new feature, no existing code to reason about
- [docs/scenarios/brownfield.md](docs/scenarios/brownfield.md) — a real bug fix with a deliberate first-attempt failure and a genuine retry
- [docs/scenarios/ambiguous.md](docs/scenarios/ambiguous.md) — a vague requirement that triggers mid-flight re-planning

## Live mode (author's own machine only)

The Coder node can call the real `claude` CLI instead of replaying fixtures. This
requires an authenticated `claude` CLI on the **host** (not something a reviewer
needs or can easily set up):

```bash
cp docker-compose.override.yml.example docker-compose.override.yml   # bind-mounts host ~/.claude
ORCHESTRATOR_MODE=live docker compose up orchestrator
```

Without this file, `--live`/`ORCHESTRATOR_MODE=live` inside Docker has no
credentials to work with and will fail clearly rather than silently falling back
to something else. This is intentional — see
[docs/architecture.md](docs/architecture.md) for the credential-boundary reasoning.

## Running without Docker

Docker Compose is the primary, tested path. If Docker isn't available:

```bash
# Orchestrator
cd orchestrator
python -m venv .venv && source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt -r ../target_app/requirements.txt
python run_all_scenarios.py   # uses an in-memory checkpointer (no POSTGRES_* set)

# Target app (separate terminal)
cd target_app
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload   # falls back to SQLite automatically
```

The brownfield scenario's concurrency regression test specifically needs real
PostgreSQL (SQLite's write-serialization doesn't reproduce the same race) — without
it, that one test skips rather than fails, and the retry arc won't be exercised.
Everything else works identically against the SQLite fallback.

## Repository layout

```
orchestrator/          LangGraph orchestration core
  state.py             GraphState — the shared state schema
  graph.py             StateGraph wiring: routing, retry/fallback/rollback/safe-stop
  tools.py             Sandboxed pytest runner, guardrail checks, git helpers
  checkpointer.py       MemorySaver (tests) / PostgresSaver (production)
  telemetry.py          Dual JSONL + console audit logging
  metrics.py             Reliability metrics (success rate, retry/rollback freq, MTTR, latency)
  nodes/                 The 9 graph nodes, one file each
  fixtures/               Captured Coder transcripts + human gate decisions (replay data)
  scenarios/              Demo entry points + shared runner
  scripts/                 Fixture-capture tooling (host-only, not part of the reviewer path)
  tests/                   Orchestrator's own test suite (102 tests, 80.8% coverage)
target_app/             The URL shortener the orchestrator builds/evolves
  app/                    FastAPI application code
  tests/                  27 tests, 97% coverage
docs/
  architecture.md         Components, orchestration model, control flow, key decisions
  final_summary.md        Plan/rationale, artifacts, risks, assumptions, limitations
  scenarios/               Per-scenario walkthroughs with real captured output
  coverage/                 pytest-cov reports + functional coverage tables
scripts/                 Product demo scripts (e.g. shorten a real URL against the running app)
docker-compose.yml       The full stack
Makefile                 One-command shortcuts (make help for the full list)
```

## Testing approach

Two independent test suites, both checked into the repo and both exercised in CI-like
fashion during development (see commit history — every commit that touches code
was tested before landing):

- **`orchestrator/tests/`** (102 tests, 80.8% coverage) — the orchestration logic
  itself: state reducers under real parallel LangGraph writes, every node's
  behavior including all four gate types, the full retry → fallback → rollback →
  safe-stop governance chain via both unit-level and end-to-end integration tests,
  and a real PostgreSQL checkpointer-durability test. Deliberately excludes the
  live `claude` CLI call itself (no auth/network dependency in a committed suite)
  and the demo scripts' I/O (validated instead by actually running them — see the
  scenario walkthroughs).
- **`target_app/tests/`** (27 tests, 97% coverage) — the URL shortener's own
  correctness: API integration tests, repository unit tests, auth enforcement,
  rate limiting (including window-expiry via a controlled clock), and DB
  connection-string construction.

See [docs/coverage/unit_coverage.md](docs/coverage/unit_coverage.md) for the full
report with reasoning for every deliberate exclusion, and
[docs/coverage/functional_coverage.md](docs/coverage/functional_coverage.md) for
scenario × requirement/API and scenario × SDLC-stage coverage tables.

## Design trade-offs made under the time constraint

This was built to a target of 6–8 hours with a hard ceiling of 10. Where a choice
had to be made between finishing faster and finishing with a more complete
orchestration/governance design, the more complete design won — the cuts below are
all in secondary polish, not in orchestration depth, human-approval-gate coverage,
or test rigor, which is where the actual evaluation weight sits.

| Area | What shipped | What a real production version would add | Why this split |
|---|---|---|---|
| Target-app auth | Lightweight shared-secret API key on write/analytics endpoints | Full user accounts, ownership, per-user audit trail | Guards the two concrete abuse vectors in scope without the time cost of a full auth system; reopened and resolved mid-build after direct review pushback — see [docs/final_summary.md](docs/final_summary.md) |
| Database schema management | `Base.metadata.create_all()` on startup | Alembic migrations | Real practice, not worth the time cost at this scope; documented rather than hidden |
| Codebase impact analysis | Deterministic keyword scan | Real static analysis / AST-level reasoning | Deliberately lightweight — it answers "what looks relevant"; actual code understanding is the LLM-powered Coder node's job |
| Rate limiting | In-process, single-container | Redis-backed, multi-instance | No horizontal scaling to coordinate across in a single-container demo |
| CI/CD pipeline | None | GitHub Actions running both test suites + coverage gates | The test suites *are* the artifact a CI pipeline would run; the pipeline config itself was out of scope for the time budget |
| Three-scenario demo workspace | Each scenario runs against its own isolated copy | One cumulative, live-evolving shared service | Tried the cumulative version first — it broke on the third scenario because two independently-captured fixtures both touched `app/main.py`. Correctness across all three demos won over the more visually impressive "watch it evolve live" narrative. Full story in [docs/architecture.md](docs/architecture.md). |

Full accounting — including every real bug found and fixed during the build, not
just the ones I chose to cut — is in
[docs/final_summary.md](docs/final_summary.md).
