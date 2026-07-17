# Functional Coverage: Scenarios × Requirements/APIs × SDLC Stages

Two readings of "functional coverage" — both covered here rather than picking one.

## 1. Requirements/APIs exercised by each scenario

| Scenario | Target-app surface exercised | Orchestrator capability demonstrated |
|---|---|---|
| **Greenfield** (QR code endpoint) | New `GET /{code}/qr` endpoint; touches `app/main.py`'s router registration; no existing endpoint's behavior changes | Requirement clarification with a real human decision; net-new component design (no impact analysis needed); task decomposition; live-LLM code generation with dependency awareness (`qrcode` package); parallel test+doc generation; guardrail scan on genuinely new code; merge with a real git commit |
| **Brownfield** (concurrency fix) | Existing `POST /shorten` → `GET /{code}` → click-count path in `app/repository.py`; the fix must preserve `URLRepository`'s existing method signatures | Codebase impact analysis (keyword scan across the real target-app tree); a **deliberate, PostgreSQL-verified** first-attempt test failure; a real bounded retry (Coder re-invoked with the failure fed back into its prompt); recovery verified by literally re-running pytest, not trusting a recorded flag; guardrail scan; merge |
| **Ambiguous** (reliability) | Whichever surface the model chooses to address a genuinely vague requirement — in the captured run: `app/db.py` (connection resilience), `app/main.py` (health check, generic error handling) | Ambiguity detection; a **deterministic, scripted** mid-flight conflict (existing `app/rate_limit.py`) triggering the Re-planner; a task list that **genuinely differs** before and after the re-planning gate (4 tasks → 5, with a reconciliation task); Coder working from that revised scope; merge |

Across all three: `POST /shorten`, `GET /{code}`, `GET /{code}/stats`, `GET /health`,
and the API-key auth guarding the first two are all exercised at least once, either
directly by a scenario's generated code or by the baseline test suite the scenario's
Test Executor run re-verifies alongside its own changes.

## 2. SDLC stages walked through by each scenario

| SDLC stage | Greenfield | Brownfield | Ambiguous |
|---|:---:|:---:|:---:|
| Requirement understanding / ambiguity surfacing | ✅ (gated) | — (unambiguous bug report) | ✅ (vague-qualifier detection) |
| Codebase reasoning / impact analysis | — (skipped, conditional edge) | ✅ (gated) | ✅ (ungated, feeds conflict detection) |
| Architecture/design | ✅ | ✅ | ✅ |
| Task decomposition | ✅ (gated: plan_approval) | ✅ (ungated) | ✅ (initial **and** revised) |
| Dynamic re-planning | — | — | ✅ (the scenario this demonstrates) |
| Code generation (live LLM) | ✅ | ✅ (2 attempts) | ✅ |
| Automated testing | ✅ (1 run, passes) | ✅ (2 runs: fail → pass) | ✅ (1 run, passes) |
| Bounded retry | — | ✅ (the scenario this demonstrates) | — |
| Fallback (retries exhausted) | — | not reached (recovered within limit) | — |
| Rollback | — | not reached (merge approved) | — |
| Safe-stop | — | not reached | — |
| Guardrail enforcement | ✅ (0 findings) | ✅ (0 findings) | ✅ (0 findings) |
| Documentation generation | ✅ | ✅ | ✅ |
| Human approval gates | clarification, plan, merge | codebase-impact, merge | re-planning, merge |
| Merge / release (real git commit) | ✅ | ✅ | ✅ |
| Audit trail / telemetry (JSONL + console) | ✅ | ✅ | ✅ |
| Reliability metrics computed | ✅ | ✅ (retry_count=1, MTTR non-zero) | ✅ |

The fallback, rollback, and safe-stop stages are **not exercised by any of the three
required demo scenarios** by design (per the confirmed scope: the brownfield
scenario recovers within the bounded retry limit, so fallback/rollback are never
reached in that demo). They are real, tested infrastructure — see
`test_graph_integration.py`'s `test_fallback_exhaustion_rolls_back`,
`test_guardrail_rejection_with_prior_commit_rolls_back_for_real`, and
`test_safe_stop_on_missing_fixture_never_reaches_release_gate` — exercised directly
through synthetic fixtures rather than through one of the three named demos, which
keeps each demo focused on the specific gate/path it's meant to showcase per the
gate-placement distribution.
