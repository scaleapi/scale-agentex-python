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

**Note — these symbols still have tutorial consumers (see item 13):** the pre-unified example agents (`examples/tutorials/.../030_langgraph`, `100_langgraph`, `040_pydantic_ai`, `110_pydantic_ai`, etc.) import `create_langgraph_tracing_handler` / `create_pydantic_ai_tracing_handler`. Deleting the symbols breaks those tutorials, so item 13 (retire/migrate them) is a hard prerequisite of this removal, not optional polish.

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
- **Naming — standardize on the numbered `NNN_<name>` paradigm** (matches every pre-existing tutorial). Rename the new harness agents off the bare `harness_*` scheme:
  - `harness_pydantic_ai` and `harness_langgraph` (the bare-named sync/async/temporal dirs) → take the numbered slots of the pre-unified tutorials they replace (`040_pydantic_ai`, `110_pydantic_ai`; `030_langgraph`, `100_langgraph`, `130_langgraph`). This is the same move as item 13's replace-in-place — do the rename and the old-tutorial retirement as one step rather than twice.
  - `060_harness_openai` / `130_harness_openai` / `140_harness_openai` → drop the `harness_` infix so they read `NNN_openai_*` like the rest, again folding into the openai retirement in item 13.
  - `harness_codex` → assign fresh `NNN_codex` numbers consistent with the sequence (net-new; no old slot to reuse).
  - `claude_code` (`060/130/140_claude_code`) already follows the numbered paradigm — no rename.
  - Because the tutorials job discovers by `manifest.yaml` glob, the renames don't need a CI/allowlist change, but update any tutorial index / README / cross-links that reference the old paths (see item 13 verification).
- **`.dockerignore`:** byte-identical in pydantic-ai/openai/claude, **absent in langgraph and codex**. Add the shared file everywhere (or none).
- **`conftest.py`:** present only in codex (one per tier). Either promote it to the shared tutorial test setup or remove if unneeded.

### 12. Decide integration-test coverage parity

Only pydantic-ai (#415) and langgraph (#417) ship `test_harness_*_{sync,async,temporal}` integration suites + CI live-matrix rows; openai/claude/codex (#416/#420/#421) ship only conformance + turn tests. Either add the missing suites (and their matrix rows — note #415's matrix comment already invites PRs 5–8 to do so) or document the intentional difference. The two existing matrix-job definitions are near-identical and should collapse to one matrix once item 6's shared fakes land.

### 13. Retire the duplicate pre-unified framework tutorials

The migrations added a **second** set of framework tutorials alongside the ones already on `next`, so langgraph / pydantic-ai / openai now each have two demonstrations of the same framework:

| Framework | Pre-existing (pre-unified, on `next`) | New (unified surface, harness PRs) |
| --- | --- | --- |
| langgraph | `00_sync/030_langgraph`, `10_async/00_base/100_langgraph`, `10_async/10_temporal/130_langgraph` | `harness_langgraph` ×3 (#417) |
| pydantic-ai | `00_sync/040_pydantic_ai`, `10_async/00_base/110_pydantic_ai`, `10_async/10_temporal/110_pydantic_ai` | `harness_pydantic_ai` ×3 (#415) |
| openai | `00_sync/050_openai_agents_local_sandbox`, `10_async/00_base/120_…`, `10_async/10_temporal/120_…` | `060/130/140_harness_openai` (#416) |

The old ones demonstrate the **deprecated pre-unified path** — verified: `040_pydantic_ai` imports `create_pydantic_ai_tracing_handler` + `convert_*(tracing_handler=...)`; `030_langgraph`/`100_langgraph` import `create_langgraph_tracing_handler` (+ `stream_langgraph_events`). The new `harness_*` agents are their unified-surface (`UnifiedEmitter` + `<Harness>Turn`) replacements. So this is the tutorial-facing half of item 1's removal.

**Decision — replace in place, numbered paradigm (settled):** port each unified-surface (`harness_*`) implementation into the numbered slot of the pre-unified tutorial it supersedes (`harness_pydantic_ai` → `040_pydantic_ai` / `110_pydantic_ai`; `harness_langgraph` → `030_langgraph` / `100_langgraph` / `130_langgraph`; `*_harness_openai` → the `NNN_openai_*` slots) and delete the old deprecated dirs. This keeps the established numbered sequence and is the same operation as item 11's rename — execute them together (the rename *is* the retirement). codex is net-new, so it takes fresh `NNN_codex` numbers; claude-code is already numbered. The rejected alternative (keep the bare `harness_*` dirs, delete the old) is not taken — it would orphan the existing numbers and leave the naming split.

For every framework: confirm the surviving agent does not import the item-1 deprecated symbols, and fix any tutorial index/README that links the removed dirs. The existing `090_claude_agents_sdk_mvp` is the Claude **Agents SDK** (not the claude-code CLI harness), so it stays.

> **Sequencing note:** items 6–9 and 11–12 are **non-breaking refactors** (tests, internal helpers, examples) — they only need the stack merged (precondition 1), NOT the deprecation window / consumer-migration gates that items 1–2 require. They can land as their own earlier cleanup PR if PR 10's breaking removals are blocked on the version-bump policy. Item 10 rides with item 3; **item 13 is gated with item 1** (the old tutorials import the symbols item 1 removes), so do them in the same PR.

(Also noted, no action: #417 already carries a `tests/lib/adk/test_pydantic_ai_async.py` change via a shared tracing-handler fix — recorded here only so it isn't mistaken for stray duplication during cleanup.)

## Verification
- Grep the whole repo (and confirm with the golden agent / known consumers) for each removed symbol — zero references before deletion.
- After the test-scaffolding consolidation (items 6–7): the shared `_fakes` module / fixture is the only definition of `_FakeTracing`/`_FakeSpan`, and the determinism test exists once — grep confirms no per-file/per-harness copies remain.
- After the turn/sync consolidation (items 8–9): the five turn modules import the shared usage helper and the sync path follows one convention; harness conformance + integration suites stay green.
- After the tutorial retirement (item 13): exactly one tutorial agent per framework per tier remains, none import the item-1 deprecated symbols, and the tutorial CI/test job + any index/README links resolve (no references to deleted dirs).
- Full `./scripts/test` on Python 3.12 AND 3.13 (run the two versions separately or in shorter scoped batches — the dual-version `./scripts/test` in one shot has tripped a 600s no-output watchdog; prefer scoped runs or background with periodic output).
- `./scripts/lint` clean (whole-repo ruff + pyright).
- Changelog / release note documenting the removal of the deprecated public symbols.

## Risk
Removing publicly-exported (deprecated) symbols is a breaking change — gate PR 10 on the version-bump policy and on confirming the golden agent + any external consumers are migrated. Everything here is recoverable from history; sequence it as the final, deliberate cleanup of the harness-surface workstream.
