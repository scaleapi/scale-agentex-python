# PR 10 — Post-Merge Harness Cleanup Plan

Date: 2026-06-22
Status: Plan — execute as **PR 10**, only AFTER the whole harness-surface stack merges and the deprecation/migration preconditions below hold.
Repo: `scale-agentex-python`

## Why this is a separate, later PR

The harness-surface stack (foundation #412, conformance #414, migrations #415/#416/#417/#420/#421, facade+docs #423) was built **additively** so nothing regressed and the stack stayed reviewable. That deliberately left behind a few transitional artifacts — deprecated-but-kept shims, resolved-workaround comments, and a flat public namespace that grew as taps were added. Removing them is a breaking-ish, cross-cutting change that should NOT happen inside the feature PRs. PR 10 does that cleanup once it's safe.

## Preconditions (do not start PR 10 until ALL hold)

1. **Entire stack merged** to `next`/main: #412, #414, #415, #416, #417, #420, #421, #423.
2. **Deprecation window observed** (or a minor/major version boundary) for the publicly-deprecated symbols below — they were only docstring-deprecated, never runtime-warned, so external code may still import them.
3. **Golden agent migrated** off the bespoke paths (per the adoption plan, #422 → implementation in `agentex-agents`): it no longer constructs the deprecated tracing handlers or any pre-unified converter path. Grep the golden agent + any other internal consumers first.
4. **No external consumers** depend on the removed symbols (check downstream usage; add a changelog/release note for the removal).

## Scope — what PR 10 removes / consolidates

### 1. Delete the deprecated bespoke tracing handlers (primary item)
These were superseded by `SpanTracer`/`UnifiedEmitter` (which derive spans from the canonical stream) and only docstring-deprecated:
- `src/agentex/lib/adk/_modules/_pydantic_ai_tracing.py` — `create_pydantic_ai_tracing_handler`, `AgentexPydanticAITracingHandler`.
- `src/agentex/lib/adk/_modules/_langgraph_tracing.py` — `create_langgraph_tracing_handler`, `AgentexLangGraphTracingHandler`.
- Any openai bespoke tracing shim deprecated in #416 (`sync_provider.py` `SyncStreamingModel`/`SyncStreamingProvider` if applicable).
Remove the modules (or the deprecated symbols), their `adk/__init__.py` exports, and all references/tests that only existed to exercise the deprecated path. Keep any genuinely-shared helpers they used if still referenced elsewhere.

### 2. Remove resolved-workaround markers and transitional comments
Now that AGX1-377/378 are fixed in the foundation and the migrations dropped their workarounds, delete the leftover transitional breadcrumbs:
- Any remaining `# AGX1-377`/`# AGX1-378` "workaround/limitation" comments in `auto_send.py`, the per-harness turns/async helpers, and the conformance runner (the coalescing is gone; `created_at` is restored; streamed tool delivery works).
- Stale docstring notes that describe behavior that has since changed (e.g. "created_at limitation", "coalescing workaround").
Keep comments that document *current* contracts; only remove ones describing now-removed transitional state.

### 3. (Optional) Introduce an `adk.harness` namespace to de-crowd the flat facade
#423 exposed the surface flat on `agentex.lib.adk` for consistency. With five `convert_<harness>_to_agentex_events` taps + `<Harness>Turn`s + `UnifiedEmitter`/types, the flat namespace is crowded. Consider a dedicated `agentex.lib.adk.harness` submodule that re-exports the surface, while keeping flat `adk.*` re-exports for one release (back-compat), then dropping the flat ones in a later major. Decide with the team; this is polish, not required. If done, update the #423 docs page (`adk/docs/harness.md`) accordingly.

### 4. Remove any vestigial simple-conformance-runner paths
All harnesses now register into the cross-channel conformance runner (#414). If, after merge, any simple/determinism-only runner code path or the standalone `derive_all`-based test remains unused, remove it (or keep `derive_all` only if it's still a useful primitive). Verify nothing imports a removed helper.

### 5. De-duplicate per-harness `_*_sync` / `_*_async` if anything remains
The async helpers (`stream_pydantic_ai_events`, `stream_langgraph_events`, `run_agent_streamed_auto_send`) now delegate to `UnifiedEmitter.auto_send_turn`. Confirm no hand-rolled `adk.streaming` streaming loops remain in those modules post-merge; remove any leftover dead branches.

### 6. Consolidate duplicated test scaffolding (cross-PR review finding)

The migration PRs were reviewed independently, so each re-introduced the same test doubles instead of sharing them. After merge these are the concrete duplicates:

- **`_FakeTracing` / `_FakeSpan`** are defined ~9 times: the foundation tests already carry three copies (`tests/lib/core/harness/test_tracer.py`, `test_emitter.py`, `conformance/runner.py`), and the integration suites add six more — `tests/lib/core/harness/test_harness_pydantic_ai_{sync,async,temporal}.py` (#415) and `test_harness_langgraph_{sync,async,temporal}.py` (#417) each redefine them.
- **`_run_yield_turn`** is duplicated between the pydantic-ai and langgraph integration suites.

Extract a single shared module — `tests/lib/core/harness/_fakes.py` (`FakeSpan`, `FakeTracing`, `run_yield_turn`) or a `conftest.py` `fake_tracing` fixture — and have every harness test import it. Delete the per-file copies.

### 7. Parametrize the generic conformance determinism test once

`test_span_derivation_is_deterministic` is copy-pasted into every per-harness conformance module (`conformance/test_<harness>_conformance.py`) on top of the copy already in the shared `conformance/test_conformance.py`. It is harness-agnostic — it only re-derives over registered fixtures. Keep ONE parametrized version in the shared conformance module driven by `all_fixtures()`, and delete the per-harness copies (the per-harness modules keep only their fixture registration + cross-channel assertions).

### 8. Extract a shared harness-turn usage-normalization helper

The five `HarnessTurn` implementations — `_pydantic_ai_turn.py`, `_langgraph_turn.py`, `providers/_modules/openai_turn.py`, `_claude_code_turn.py`, `_codex_turn.py` (134–214 lines each) — are not copy-paste, but they repeat the same shape: wrap a tap's event stream and normalize provider usage into `TurnUsage`. Pull the common normalization into a shared primitive in the foundation (e.g. `core/harness/usage.py` `normalize_usage(...)` or a `HarnessTurnBase` mixin), leaving each module only its provider-specific mapping. Do NOT force-fit harnesses whose usage shape genuinely diverges (codex is the largest for a reason — check before collapsing).

### 9. Converge the three sync-path structures

"Sync delivery" was implemented three different ways across the migrations: openai modifies `providers/_modules/sync_provider.py` + adds `openai_turn.py`; pydantic-ai/langgraph modify their existing `_*_sync.py`; claude/codex add new `_claude_code_sync.py` / `_codex_sync.py`. Pick one structural convention and align the five harnesses to it so the sync path reads the same everywhere. (Overlaps item 5 — do them together.)

### 10. Reconcile the competing `adk/__init__.py` edits

`src/agentex/lib/adk/__init__.py` is edited by three PRs — claude (#420, +9), codex (#421, +6), and the facade (#423, +22). Once merged, the facade in #423 should be the single source of the public surface; fold the claude/codex ad-hoc export additions into it and drop the duplicates. (Subsumed by the facade work in item 3 — track here so it isn't missed.)

### 11. Tutorial-agent consistency pass

The 15 tutorial projects (5 harnesses × sync/async/temporal) are intentionally tailored per harness, so there is no code to dedupe — but the scaffolding drifted and should be standardized:
- **Naming:** `harness_<x>` (pydantic-ai, langgraph, codex) vs numeric prefixes `060_/130_/140_` (openai, claude_code). Pick one convention and rename.
- **`.dockerignore`:** byte-identical in pydantic-ai/openai/claude, **absent in langgraph and codex**. Add the shared file everywhere (or none).
- **`conftest.py`:** present only in codex (one per tier). Either promote it to the shared tutorial test setup or remove if unneeded.

### 12. Decide integration-test coverage parity

Only pydantic-ai (#415) and langgraph (#417) ship `test_harness_*_{sync,async,temporal}` integration suites + CI live-matrix rows; openai/claude/codex (#416/#420/#421) ship only conformance + turn tests. Either add the missing suites (and their matrix rows — note #415's matrix comment already invites PRs 5–8 to do so) or document the intentional difference. The two existing matrix-job definitions are near-identical and should collapse to one matrix once item 6's shared fakes land.

> **Sequencing note:** items 6–9 and 11–12 are **non-breaking refactors** (tests, internal helpers, examples) — they only need the stack merged (precondition 1), NOT the deprecation window / consumer-migration gates that items 1–2 require. They can land as their own earlier cleanup PR if PR 10's breaking removals are blocked on the version-bump policy. Item 10 rides with item 3.

(Also noted, no action: #417 already carries a `tests/lib/adk/test_pydantic_ai_async.py` change via a shared tracing-handler fix — recorded here only so it isn't mistaken for stray duplication during cleanup.)

## Verification
- Grep the whole repo (and confirm with the golden agent / known consumers) for each removed symbol — zero references before deletion.
- After the test-scaffolding consolidation (items 6–7): the shared `_fakes` module / fixture is the only definition of `_FakeTracing`/`_FakeSpan`, and the determinism test exists once — grep confirms no per-file/per-harness copies remain.
- After the turn/sync consolidation (items 8–9): the five turn modules import the shared usage helper and the sync path follows one convention; harness conformance + integration suites stay green.
- Full `./scripts/test` on Python 3.12 AND 3.13 (run the two versions separately or in shorter scoped batches — the dual-version `./scripts/test` in one shot has tripped a 600s no-output watchdog; prefer scoped runs or background with periodic output).
- `./scripts/lint` clean (whole-repo ruff + pyright).
- Changelog / release note documenting the removal of the deprecated public symbols.

## Risk
Removing publicly-exported (deprecated) symbols is a breaking change — gate PR 10 on the version-bump policy and on confirming the golden agent + any external consumers are migrated. Everything here is recoverable from history; sequence it as the final, deliberate cleanup of the harness-surface workstream.
