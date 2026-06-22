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

## Verification
- Grep the whole repo (and confirm with the golden agent / known consumers) for each removed symbol — zero references before deletion.
- Full `./scripts/test` on Python 3.12 AND 3.13 (run the two versions separately or in shorter scoped batches — the dual-version `./scripts/test` in one shot has tripped a 600s no-output watchdog; prefer scoped runs or background with periodic output).
- `./scripts/lint` clean (whole-repo ruff + pyright).
- Changelog / release note documenting the removal of the deprecated public symbols.

## Risk
Removing publicly-exported (deprecated) symbols is a breaking change — gate PR 10 on the version-bump policy and on confirming the golden agent + any external consumers are migrated. Everything here is recoverable from history; sequence it as the final, deliberate cleanup of the harness-surface workstream.
