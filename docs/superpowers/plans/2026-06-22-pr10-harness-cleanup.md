# PR 10 — Post-Merge Harness Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the transitional artifacts left behind by the additive harness-surface stack (deprecated tracing handlers, resolved-workaround comments, duplicated test scaffolding, divergent per-harness structures), consolidate the harness source/test/tutorial filesystem onto one convention, retire the duplicate pre-unified tutorials, and bring `adk/docs/harness.md` in line with the final merged surface.

**Architecture:** The harness-surface stack (#412 foundation, #414 conformance, #415/#416/#417/#420/#421 migrations, #423 facade+docs) was built additively so nothing regressed and each PR stayed reviewable. PR 10 is the single, deliberate cleanup that runs once the whole stack is merged and the deprecation/migration preconditions hold. Work is ordered so non-breaking refactors land first and the breaking removals (deprecated public symbols + the tutorials that import them) land last, behind the version-bump gate.

**Tech Stack:** Python 3.12/3.13, `rye`/`uv`, `pytest`, `ruff`, `pyright`/`mypy`, Temporal, pydantic. Tutorials use per-project `uv` envs.

> **Branch / base:** This plan lives on `declan-scale/pr10-harness-cleanup`, **stacked on top of `declan-scale/pr9-harness-cleanup` (PR 9, #423)**, which is itself rebased onto the latest `next`. The migration stack (#412/#414–#421) is **already merged** to `next`; PR 9 (the public adk facade + `adk/docs/harness.md`) is the base of this branch. Because PR 9 is the base, the facade and `harness.md` are already present here, so the facade-reconciliation (C1/C2) and `harness.md` (C3) tasks are directly actionable. When PR 9 merges into `next`, rebase this branch onto `next` (the PR 9 commits drop out as already-merged).

> **Altitude note (read before executing):** This plan pins **exact file paths, the concrete transformation, and exact verification commands** — all verified against the merged `next` tree as of 2026-06-22. It deliberately does **not** hardcode line numbers (they drift as batches land). Where a step says "resolve at execution," run the named grep against the current tree first, then apply the described change.

---

## Preconditions (do not start the BREAKING batches until ALL hold)

1. **#423 (PR 9) is the base of this branch** — the facade + `harness.md` are present here, and the whole migration stack (#412/#414–#421) is already merged to `next`. When PR 9 merges to `next`, rebase this branch onto `next` before the breaking batches land.
2. **Deprecation window observed** (or a minor/major version boundary) for the publicly-deprecated symbols below — they were only docstring-deprecated, never runtime-warned, so external code may still import them.
3. **Golden agent migrated** off the bespoke paths (per the adoption plan, #422 → implementation in `agentex-agents`): it no longer constructs the deprecated tracing handlers or any pre-unified converter path. Grep the golden agent + any other internal consumers first.
4. **No external consumers** depend on the removed symbols (check downstream usage; add a changelog/release note for the removal).

**Optional split:** Batches A–D, G, and the stale-doc removals are **non-breaking** (tests, internal helpers, docs, integration coverage) — they only need precondition 1. If the breaking removals (Batches E, F, I) are blocked on the version-bump policy, land the non-breaking batches as an earlier cleanup PR and keep E/F/I for PR 10.

---

## Execution order

| Batch | Items | Breaking? | Gated on |
|---|---|---|---|
| A — Test scaffolding consolidation | 6, 7 | No | Precond. 1 |
| B — Internal helper / sync-path consolidation | 5, 8, 9 | No | Precond. 1 |
| C — Facade reconciliation + harness.md doc update | 10, 3 | No (additive namespace) | Precond. 1 (PR 9 merged) |
| D — Conformance vestigial cleanup | 4 | No | Precond. 1 |
| G — Integration-test parity | 12 | No | Precond. 1 |
| E — Tutorial standardization + retirement | 11, 13 | Yes (deletes dirs) | Precond. 1–4 (rides with F) |
| F — Deprecated tracing-handler + workaround removal | 1, 2 | Yes (public symbols) | Precond. 1–4 |
| I — Filesystem layout + naming consolidation | NEW | Yes (file moves + import changes) | After E/F (and Precond. 1–4) |
| H — Final docs + changelog + stale-doc removal | — | — | After E/F/I land |

Run A → B → D → G first (green, non-breaking). C lands once PR 9 is merged. Then E + F together (the old tutorials import the symbols F removes — they MUST land in the same commit range), then I (the final structural sweep, after `_tracing.py` is already gone), then H.

---

## Batch A — Consolidate duplicated test scaffolding (items 6, 7)

### Task A1: Extract the shared harness test fakes

Verified copies on `next`: `_FakeTracing` is defined in 7 places and `_FakeSpan` in 6; `_run_yield_turn` in 2. There are also near-variants under `tests/lib/adk/` (`_FakeTracingBackend`).

**Files:**
- Create: `tests/lib/core/harness/_fakes.py`
- Modify (delete local copy, import from `_fakes`): `tests/lib/core/harness/test_tracer.py`, `tests/lib/core/harness/test_emitter.py`, `tests/lib/core/harness/conformance/runner.py`, `tests/lib/core/harness/test_harness_pydantic_ai_sync.py`, `..._async.py`, `tests/lib/core/harness/test_harness_langgraph_sync.py`, `..._async.py`, `tests/lib/adk/test_pydantic_ai_sync_unified.py`, `tests/lib/adk/test_langgraph_sync_unified.py`

- [ ] **Step 1: Grep the tree for every definition site**

Run: `grep -rn "class _FakeTracing\|class _FakeSpan\|class _FakeTracingBackend\|def _run_yield_turn" tests/`
Confirm the full set before changing anything. Note `_FakeTracingBackend` (in `test_langgraph_sync_unified.py`) — decide if it is the same shape (fold it) or genuinely different (leave it, document why).

- [ ] **Step 2: Create `_fakes.py` from the canonical copy**

Lift the definitions from `tests/lib/core/harness/test_tracer.py` (the foundation copy) verbatim into `tests/lib/core/harness/_fakes.py`, exported as public names `FakeSpan`, `FakeTracing`, `run_yield_turn` (drop the leading underscore now that they are shared). This is a move, not a rewrite.

- [ ] **Step 3: Replace each local copy with an import**

In each file from the Files list, delete the local class/func block and add `from tests.lib.core.harness._fakes import FakeSpan, FakeTracing, run_yield_turn` (import only what that file uses). Update references (`_FakeTracing` → `FakeTracing`, etc.). The `tests/lib/adk/*_sync_unified.py` files import across packages — confirm the import path resolves under the test rootdir.

- [ ] **Step 4: Verify no copies remain**

Run: `grep -rn "class _FakeTracing\|class _FakeSpan\|def _run_yield_turn" tests/`
Expected: zero matches (only `_fakes.py`'s `class FakeTracing`/`class FakeSpan`/`def run_yield_turn`, which this grep does not match).

- [ ] **Step 5: Run the harness + adk test suites**

Run: `uv run --all-packages --all-extras pytest tests/lib/core/harness/ tests/lib/adk/ -q`
Expected: same pass count as pre-change, zero failures.

- [ ] **Step 6: Lint + commit**

Run: `uv run ruff check tests/`
```bash
git add tests/
git commit -m "test(harness): extract shared FakeSpan/FakeTracing/run_yield_turn fakes"
```

### Task A2: Parametrize the conformance determinism test once

Verified on `next`: `def test_span_derivation_is_deterministic` exists in `conformance/test_conformance.py` (shared), `test_langgraph_conformance.py`, and `test_pydantic_ai_conformance.py`. **Additionally**, `test_codex_conformance.py` carries the same determinism assertion (`assert derive_all(x) == derive_all(x)`) under its own test — so grep for the assertion, not just the function name.

**Files:**
- Modify: `tests/lib/core/harness/conformance/test_conformance.py` (keep the single parametrized test)
- Modify: each `tests/lib/core/harness/conformance/test_<harness>_conformance.py` (delete its determinism copy, keep fixture registration + cross-channel assertions)

- [ ] **Step 1: Grep for every determinism copy**

Run: `grep -rn "test_span_derivation_is_deterministic\|derive_all(.*) == derive_all" tests/lib/core/harness/conformance/`
Expected: the shared copy in `test_conformance.py` plus per-harness copies (currently langgraph, pydantic-ai, codex; check openai/claude too).

- [ ] **Step 2: Make the shared copy parametrized over all fixtures**

In `test_conformance.py`, ensure `test_span_derivation_is_deterministic` is parametrized by `all_fixtures()` (the registry the conformance runner exposes via `register`) so one test re-derives `derive_all(...)` over every registered fixture and asserts identical output across repeated derivation. It must reference no harness-specific symbol.

- [ ] **Step 3: Delete the per-harness copies**

Remove the determinism test/assertion from every `test_<harness>_conformance.py`, leaving those modules with only fixture registration + cross-channel assertions. Keep `derive_all` itself in `runner.py` — it is the shared primitive the parametrized test uses (NOT vestigial; see Batch D).

- [ ] **Step 4: Verify exactly one definition remains**

Run: `grep -rn "def test_span_derivation_is_deterministic" tests/lib/core/harness/conformance/`
Expected: exactly one match, in `test_conformance.py`.

- [ ] **Step 5: Run conformance tests + commit**

Run: `uv run --all-packages --all-extras pytest tests/lib/core/harness/conformance/ -q`
```bash
git add tests/lib/core/harness/conformance/
git commit -m "test(harness): parametrize the conformance determinism test once over all_fixtures()"
```

---

## Batch B — Consolidate internal helpers + sync paths (items 5, 8, 9)

### Task B1: Remove leftover hand-rolled streaming branches (item 5)

**Files (resolve exact branches at execution):** `src/agentex/lib/adk/_modules/_pydantic_ai_async.py`, `_langgraph_async.py`, and any openai/claude/codex async helper.

- [ ] **Step 1: Confirm async helpers delegate to the emitter**

Run: `grep -rn "auto_send_turn\|streaming_task_message_context\|adk.streaming" src/agentex/lib/adk/_modules/_*_async.py src/agentex/lib/adk/providers/_modules/`
Expected: `stream_*_events` / `run_agent_streamed_auto_send` call `UnifiedEmitter.auto_send_turn`. Flag any remaining hand-rolled `adk.streaming` loop as dead.

- [ ] **Step 2: Delete the dead branches** the emitter delegation made unreachable. Do not touch a live delivery route.

- [ ] **Step 3: Verify + commit**

Run: `uv run --all-packages --all-extras pytest tests/lib/core/harness/ tests/lib/adk/ -q`
```bash
git add src/agentex/lib/adk/
git commit -m "refactor(harness): drop dead hand-rolled streaming branches now covered by auto_send_turn"
```

### Task B2: Extract a shared usage-normalization primitive (item 8)

The five `HarnessTurn` impls (`_pydantic_ai_turn.py`, `_langgraph_turn.py`, `providers/_modules/openai_turn.py`, `_claude_code_turn.py`, `_codex_turn.py`) repeat the same shape: wrap a tap's event stream + normalize provider usage into `TurnUsage`.

**Files:**
- Create: `src/agentex/lib/core/harness/usage.py` (`normalize_usage(...)`) — or a `HarnessTurnBase` mixin in `core/harness/types.py`
- Create: `tests/lib/core/harness/test_usage.py`
- Modify: the five turn modules

- [ ] **Step 1: Diff the five turn impls** for the common shape.

Run: `wc -l src/agentex/lib/adk/_modules/_pydantic_ai_turn.py src/agentex/lib/adk/_modules/_langgraph_turn.py src/agentex/lib/adk/providers/_modules/openai_turn.py src/agentex/lib/adk/_modules/_claude_code_turn.py src/agentex/lib/adk/_modules/_codex_turn.py`
Note the existing `claude_code_usage_to_turn_usage` / `codex_usage_to_turn_usage` helpers — these are exactly the per-harness normalizers to converge.

- [ ] **Step 2: Write the shared primitive (TDD).** Add `test_usage.py` asserting `normalize_usage` maps representative provider usage into the correct `TurnUsage` fields (aligning with `agentex.lib.core.observability.llm_metrics`). Implement `usage.py` to pass.

Run: `uv run --all-packages --all-extras pytest tests/lib/core/harness/test_usage.py -q` → PASS.

- [ ] **Step 3: Route each turn module through the primitive,** leaving only provider-specific mapping. Do NOT force-fit a harness whose usage genuinely diverges (check codex — it is the largest for a reason; document if you skip it).

- [ ] **Step 4: Verify + commit**

Run: `uv run --all-packages --all-extras pytest tests/lib/core/harness/ tests/lib/adk/ -q`
```bash
git add src/agentex/lib/core/harness/usage.py tests/lib/core/harness/test_usage.py src/agentex/lib/adk/
git commit -m "refactor(harness): extract shared TurnUsage normalization primitive"
```

### Task B3: Converge the sync-path structures (item 9 — overlaps Batch I)

"Sync delivery" was built three ways: openai patches `providers/_modules/sync_provider.py` (+ `openai_turn.py`); pydantic-ai/langgraph use `_*_sync.py`; claude/codex use `_claude_code_sync.py`/`_codex_sync.py`.

- [ ] **Step 1: Adopt the per-harness `_<harness>_sync.py` convention** (the majority pattern, and the target end-state in Batch I). Document the choice in the commit body.
- [ ] **Step 2: Align openai to it** — this is the structural half of Batch I's openai relocation; do them together (Task I2).
- [ ] **Step 3: Verify + commit**

Run: `uv run --all-packages --all-extras pytest tests/lib/core/harness/ tests/lib/adk/ -q`
```bash
git add src/agentex/lib/adk/
git commit -m "refactor(harness): converge the five sync paths on the _<harness>_sync.py convention"
```

---

## Batch C — Reconcile the facade + update harness.md (items 10, 3) — needs PR 9 merged

### Task C1: Fold the claude/codex ad-hoc exports into the #423 facade (item 10)

Verified on `next` (pre-PR-9): `adk/__init__.py` already exports ad-hoc per-harness symbols — `convert_claude_code_to_agentex_events`, `ClaudeCodeTurn`, `claude_code_usage_to_turn_usage`, `convert_codex_to_agentex_events`, `CodexTurn`, `codex_usage_to_turn_usage` (plus the existing pydantic/langgraph taps + the deprecated `create_*_tracing_handler`). PR 9 adds the unified facade block (`UnifiedEmitter`, `SpanTracer`, `HarnessTurn`, `OpenSpan`, `CloseSpan`, `SpanSignal`, `StreamTaskMessage`, `TurnUsage`, `TurnResult`).

**Files:** `src/agentex/lib/adk/__init__.py`

- [ ] **Step 1: After rebasing onto PR-9'd `next`,** grep the facade region:

Run: `grep -n "harness\|UnifiedEmitter\|convert_.*_to_agentex_events\|Turn\b\|usage_to_turn_usage" src/agentex/lib/adk/__init__.py`

- [ ] **Step 2: Deduplicate.** Ensure every public harness symbol is imported once and listed once in `__all__`, organized under the unified facade block from #423. Remove duplicate import lines / `__all__` entries. Preserve the `# ruff: noqa: I001` ordering comment and the circular-import-safe ordering.

- [ ] **Step 3: Verify the surface imports cleanly**

Run: `uv run --all-packages python -c "import agentex.lib.adk as adk; assert len(adk.__all__) == len(set(adk.__all__)), 'dupes'; print('ok')"`
Expected: `ok`.

- [ ] **Step 4: Lint + commit**

Run: `uv run ruff check src/agentex/lib/adk/__init__.py && uv run pyright src/agentex/lib/adk/__init__.py`
```bash
git add src/agentex/lib/adk/__init__.py
git commit -m "refactor(adk): fold claude/codex exports into the single #423 harness facade"
```

### Task C2: (Decision-gated) Introduce the `adk.harness` namespace (item 3)

> Team decision required; polish, not required. If declined, skip and record it in the PR body; `harness.md` keeps the flat `agentex.lib.adk` paths.

**Files (if adopted):** Create `src/agentex/lib/adk/harness.py` (re-export the surface + taps); modify `adk/__init__.py` to keep flat re-exports for one release (back-compat).

- [ ] **Step 1:** Create the namespace re-exporting `UnifiedEmitter`, `SpanTracer`, `HarnessTurn`, `OpenSpan`, `CloseSpan`, `SpanSignal`, `StreamTaskMessage`, `TurnUsage`, `TurnResult`, and each `convert_<harness>_to_agentex_events` tap.
- [ ] **Step 2:** Keep flat `adk.*` re-exports with a comment they're retained for one release, slated to drop in a later major.
- [ ] **Step 3: Verify both paths**

Run: `uv run --all-packages python -c "from agentex.lib.adk.harness import UnifiedEmitter; from agentex.lib.adk import UnifiedEmitter; print('ok')"`
- [ ] **Step 4: Commit** (`refactor(adk): add adk.harness namespace, keep flat re-exports for back-compat`).

### Task C3: Update `adk/docs/harness.md` to the final merged surface (MANDATORY)

> Explicitly requested: keep `harness.md` up to date and update the docs in PR 10.

**Files:** `adk/docs/harness.md` (arrives via PR 9)

- [ ] **Step 1: Complete the taps table.** Replace "Taps for claude-code and codex will be added in subsequent PRs (AGX1-420, AGX1-421)" with the merged reality — list all five shipped harnesses (pydantic-ai, LangGraph, OpenAI Agents, claude-code, codex), each with its `convert_<harness>_to_agentex_events` tap, all exported from `agentex.lib.adk`. Remove the "will be added" sentence.

- [ ] **Step 2: Fix the sync ACP example.** The current "Sync ACP (pydantic-ai tap)" example builds a `UnifiedEmitter` then yields the tap directly, leaving the emitter unused (Greptile flagged this on #423) under a "pre-unified sync path" caveat. Replace with the canonical post-migration flow:

```python
import agentex.lib.adk as adk
from agentex.lib.adk import UnifiedEmitter, PydanticAITurn  # Turn wrapper implements HarnessTurn

@acp.on_message_send
async def handle(params):
    task_id = params.task.id
    async with adk.tracing.span(trace_id=task_id, name="message", ...) as turn_span:
        emitter = UnifiedEmitter(
            task_id=task_id,
            trace_id=task_id,
            parent_span_id=turn_span.id if turn_span else None,
        )
        turn = PydanticAITurn(pydantic_stream)
        async for event in emitter.yield_turn(turn):
            yield event
```

Delete the "For the pre-unified sync path the tap is still yielded directly..." paragraph.

- [ ] **Step 3: Reconcile import paths with the C2 decision.** If `adk.harness` adopted, show it as primary in the import block + examples (note flat path retained one release). Else leave flat paths.

- [ ] **Step 4: Reflect the Batch I module layout** if I lands before H — any path references in the doc (e.g. "implementation lives at `src/agentex/lib/core/harness/`") stay correct, but if examples name `_modules` paths, update to the consolidated `_<harness>_sync.py`/`_<harness>_turn.py` names.

- [ ] **Step 5: Guard against dangling references**

Run: `grep -n "create_langgraph_tracing_handler\|create_pydantic_ai_tracing_handler\|AgentexLangGraphTracingHandler\|AgentexPydanticAITracingHandler" adk/docs/harness.md`
Expected: zero (so Batch F's removals leave no dangling doc reference).

- [ ] **Step 6: Commit**

```bash
git add adk/docs/harness.md
git commit -m "docs(harness): update harness.md to the final merged surface (all taps, canonical yield_turn example)"
```

---

## Batch D — Remove vestigial conformance paths (item 4)

Note: `derive_all` (in `conformance/runner.py`) is **actively used** by the determinism tests — keep it. Look only for genuinely unreferenced simple/determinism-only runner code.

- [ ] **Step 1: Find unused runner paths**

Run: `grep -rn "derive_all\|simple_runner\|determinism_only\|run_cross_channel" tests/lib/core/harness/ src/agentex/lib/core/harness/`
For each hit, confirm whether anything still imports it after the cross-channel runner (#414) became the single entry point.

- [ ] **Step 2: Remove dead paths** nothing imports. Keep `derive_all` and `run_cross_channel_conformance` (live).

- [ ] **Step 3: Verify + commit**

Run: `uv run --all-packages --all-extras pytest tests/lib/core/harness/conformance/ -q`
```bash
git add tests/lib/core/harness/
git commit -m "test(harness): remove vestigial simple-conformance-runner paths"
```

---

## Batch G — Integration-test coverage parity (item 12)

Verified: only pydantic-ai + langgraph ship `test_harness_*_{sync,async,temporal}` suites. openai/claude/codex ship only conformance + turn/sync tests.

**Files:**
- Create (if adding parity): `tests/lib/core/harness/test_harness_openai_{sync,async,temporal}.py`, `..._claude_code_{...}.py`, `..._codex_{...}.py`
- Modify: the harness live-matrix workflow (collapse the two near-identical matrix jobs into one)

- [ ] **Step 1: Decide parity vs documented difference** (with the team). Either add the missing suites mirroring the pydantic-ai shape (importing the Batch A `_fakes`), or document the intentional gap in `harness.md` / a test README.
- [ ] **Step 2 (if adding): write them against the shared fakes.**

Run: `uv run --all-packages --all-extras pytest tests/lib/core/harness/ -q` → green.
- [ ] **Step 3: Collapse the two matrix jobs into one** parametrized matrix (enabled now that fakes are shared).

Run: `grep -rn "matrix\|harness" .github/workflows/*.yml`
- [ ] **Step 4: Commit**

```bash
git add tests/lib/core/harness/ .github/workflows/
git commit -m "test(harness): add integration-suite parity and collapse the live matrix to one job"
```

---

## Batch E — Tutorial standardization + retirement (items 11, 13) — BREAKING

> Gated with Batch F: the surviving tutorials must not import the symbols F removes; the old tutorials deleted here are the ones that DO import them. Execute E and F in the same commit range.

Verified dual tutorial sets on `next`:

| Framework | Pre-unified (RETIRE) | Unified-surface (KEEP, rename into slot) |
|---|---|---|
| langgraph | `00_sync/030_langgraph`, `10_async/00_base/100_langgraph`, `10_async/10_temporal/130_langgraph` | `harness_langgraph` ×3 |
| pydantic-ai | `00_sync/040_pydantic_ai`, `10_async/00_base/110_pydantic_ai`, `10_async/10_temporal/110_pydantic_ai` | `harness_pydantic_ai` ×3 |
| openai | `00_sync/050_openai_agents_local_sandbox`, `10_async/00_base/120_openai_agents_local_sandbox`, `10_async/10_temporal/120_openai_agents_local_sandbox` | `060_harness_openai`, `130_harness_openai`, `140_harness_openai` |
| claude-code | — (none; already numbered) | `060/130/140_claude_code` — KEEP, no rename |
| codex | — (net-new) | `harness_codex` ×3 → fresh `NNN_codex` numbers |

`090_claude_agents_sdk_mvp` is the Agents SDK (not the claude-code harness) — KEEP untouched.

### Task E1: Replace-in-place onto the numbered `NNN_<name>` paradigm

- [ ] **Step 1: Inventory** — `find examples/tutorials -name manifest.yaml | sort`. Confirm both sets above exist.
- [ ] **Step 2: Confirm the old dirs use the deprecated path**

Run: `grep -rln "create_langgraph_tracing_handler\|create_pydantic_ai_tracing_handler\|stream_langgraph_events\|stream_pydantic_ai_events" examples/tutorials/`
Expected: the pre-unified dirs (the ones to retire) show up.

- [ ] **Step 3: Replace in place, one framework at a time.** For each framework, `git rm -r` the pre-unified dir AND `git mv` the unified `harness_*` dir into that exact slot — both halves are required, or the old dir lingers and the tier ends up with two tutorials for the same framework. Mapping (left = source dir to move, right = old dir to delete + destination path):
  - `harness_pydantic_ai` → replaces `00_sync/040_pydantic_ai`, `10_async/00_base/110_pydantic_ai`, `10_async/10_temporal/110_pydantic_ai`
  - `harness_langgraph` → replaces `00_sync/030_langgraph`, `10_async/00_base/100_langgraph`, `10_async/10_temporal/130_langgraph`
  - `060_harness_openai`/`130_harness_openai`/`140_harness_openai` → **delete the old `*_openai_agents_local_sandbox` dirs** (`00_sync/050_…`, `10_async/00_base/120_…`, `10_async/10_temporal/120_…`) and move the harness_openai dirs into those slots, renamed `050_openai_agents` / `120_openai_agents` (drops the `harness_` infix AND the 060/130/140 collision with `claude_code`). Do NOT merely rename `060_harness_openai`→`060_openai` — that would leave the old `050_openai_agents_local_sandbox` in place.
  - `harness_codex` ×3 → fresh `NNN_codex` numbers consistent with the sequence (`070`/`140`/`150`); no old dir to delete

- [ ] **Step 4: Confirm survivors are clean**

Run: `grep -rln "create_langgraph_tracing_handler\|create_pydantic_ai_tracing_handler" examples/tutorials/`
Expected: zero matches.

- [ ] **Step 5: Standardize per-tutorial scaffolding (item 11).** Add the shared `.dockerignore` to the langgraph + codex tutorials (byte-identical to the pydantic-ai/openai/claude copy). Decide `conftest.py` (present only in codex): promote to shared test setup or remove — apply uniformly.

- [ ] **Step 6: Fix index/README cross-links**

Run: `grep -rln "harness_pydantic_ai\|harness_langgraph\|harness_openai\|harness_codex" examples/ docs/ README.md`
Update every reference to the new numbered path. Expected after: zero stale references.

- [ ] **Step 7: Confirm glob discovery unaffected**

Run: `grep -n "harness_\|030_langgraph\|040_pydantic_ai\|050_openai" .github/workflows/agentex-tutorials-test.yml`
Expected: no hardcoded references to renamed/removed dirs (discovery is by `manifest.yaml` glob).

- [ ] **Step 8: Commit** combined with Batch F (Task F3).

---

## Batch F — Remove deprecated tracing handlers + workaround markers (items 1, 2) — BREAKING

### Task F1: Delete the deprecated bespoke tracing handlers (item 1)

**Files:**
- Delete: `src/agentex/lib/adk/_modules/_pydantic_ai_tracing.py` (`create_pydantic_ai_tracing_handler`, `AgentexPydanticAITracingHandler`)
- Delete: `src/agentex/lib/adk/_modules/_langgraph_tracing.py` (`create_langgraph_tracing_handler`, `AgentexLangGraphTracingHandler`)
- Modify: `src/agentex/lib/adk/__init__.py` (remove the two imports + two `__all__` entries)
- Delete: tests that exist only to exercise the deprecated path

> **⚠ openai shim is NOT in this task.** `SyncStreamingModel`/`SyncStreamingProvider` in `providers/_modules/sync_provider.py` are **load-bearing** — referenced by the live CLI template `src/agentex/lib/cli/templates/sync-openai-agents/project/acp.py.j2`. They are the supported sync-openai delivery path, not a deprecated tracing shim. Do NOT delete them here. Their relocation/renaming is handled in Batch I (Task I2) and only after the template is updated.

- [ ] **Step 1: Prove zero live references**

Run: `grep -rn "create_langgraph_tracing_handler\|create_pydantic_ai_tracing_handler\|AgentexLangGraphTracingHandler\|AgentexPydanticAITracingHandler" src/ tests/ examples/`
Expected after Batch E: matches only in the modules being deleted, their dedicated tests, and `adk/__init__.py`. If anything else matches (esp. the golden agent), STOP — precondition 3 unmet.

- [ ] **Step 2: Delete the modules + exports.** `git rm` both `_*_tracing.py`. In `adk/__init__.py` remove the two `from ..._*_tracing import create_*_tracing_handler` lines and the two `"create_*_tracing_handler"` `__all__` entries. Delete the dedicated deprecated-path tests. Keep any genuinely-shared helper they used if still referenced (grep first).

- [ ] **Step 3: Verify**

Run: `grep -rn "create_langgraph_tracing_handler\|create_pydantic_ai_tracing_handler" src/ tests/ examples/` → zero.
Run: `uv run --all-packages python -c "import agentex.lib.adk as adk; print('ok')"` → `ok`.

### Task F2: Remove resolved-workaround markers + stale docstrings (item 2)

Verified on `next`: many `AGX1-377`/`AGX1-378` references exist across `_langgraph_async.py`, `_langgraph_sync.py`, `_langgraph_turn.py`, `_pydantic_ai_turn.py`, `core/harness/auto_send.py`, `core/services/adk/providers/openai.py`, the conformance runner, and many test docstrings. **Most describe the LANDED fix / current contract** (e.g. "AGX1-377 fix: auto_send now delivers streamed tool-request messages", "AGX1-378 restored: created_at is now threaded through", "LangGraph emits tool requests as Full events").

**Files (resolve at execution):** `src/agentex/lib/core/harness/auto_send.py`, the per-harness turn/async/sync modules, `src/agentex/lib/core/services/adk/providers/openai.py`, the conformance runner, and test docstrings.

- [ ] **Step 1: Find the breadcrumbs**

Run: `grep -rn "AGX1-377\|AGX1-378\|workaround\|coalescing\|created_at limitation" src/ tests/`

- [ ] **Step 2: Trim the historical framing, keep the current contract.** For each hit: if it documents *why the code currently behaves this way* (e.g. LangGraph Full-event tool requests, `created_at` threading) keep the explanation but strip the now-meaningless ticket-number / "workaround"/"note:" framing. Delete only comments describing removed transitional state. **No code-behavior change in this task** — comments/docstrings only.

- [ ] **Step 3: Verify**

Run: `grep -rn "AGX1-377\|AGX1-378" src/ tests/`
Expected: zero (or only deliberately-kept current-contract notes, justified in the commit body).

### Task F3: Verify the breaking batch + commit E+F together

- [ ] **Step 1:** `uv run --all-packages --all-extras pytest tests/lib/core/harness/ tests/lib/adk/ -q` → green.
- [ ] **Step 2:** `uv run ruff check src/agentex/lib/adk/ src/agentex/lib/core/harness/ && uv run pyright src/agentex/lib/adk/__init__.py` → clean.
- [ ] **Step 3: Commit the breaking set**

```bash
git add -A
git commit -m "refactor(harness)!: remove deprecated tracing handlers, retire pre-unified tutorials, drop resolved-workaround markers

BREAKING CHANGE: removes the docstring-deprecated create_langgraph_tracing_handler /
create_pydantic_ai_tracing_handler and their handler classes from the public adk surface.
Use UnifiedEmitter + the convert_<harness>_to_agentex_events taps instead."
```

---

## Batch I — Filesystem layout + naming consolidation (NEW) — BREAKING

The harness modules landed in different spots with different names. Target end-state (per the directive: **every provider has just a `sync.py` and a `turn.py`, all under `adk/_modules/`, openai pulled out of `providers/_modules/`**):

| Harness | Final source files (all under `src/agentex/lib/adk/_modules/`) |
|---|---|
| pydantic-ai | `_pydantic_ai_sync.py`, `_pydantic_ai_turn.py` |
| langgraph | `_langgraph_sync.py`, `_langgraph_turn.py` |
| claude-code | `_claude_code_sync.py`, `_claude_code_turn.py` (already correct) |
| codex | `_codex_sync.py`, `_codex_turn.py` (already correct) |
| openai | `_openai_sync.py`, `_openai_turn.py` (MOVED from `providers/_modules/`) |

Removed/folded by this batch (or already by F): `_pydantic_ai_async.py`, `_langgraph_async.py`, `_langgraph_messages.py`, `_pydantic_ai_tracing.py` (F), `_langgraph_tracing.py` (F), and the `providers/_modules/openai_turn.py` + `sync_provider.py` (relocated/renamed).

### Task I1: Collapse pydantic-ai / langgraph to `sync.py` + `turn.py`

**Files:**
- Modify/remove: `src/agentex/lib/adk/_modules/_pydantic_ai_async.py`, `_langgraph_async.py`, `_langgraph_messages.py`
- Modify: `_pydantic_ai_sync.py`, `_pydantic_ai_turn.py`, `_langgraph_sync.py`, `_langgraph_turn.py`, `adk/__init__.py`

> **Caveat — the async helpers are public.** `stream_pydantic_ai_events`, `stream_langgraph_events`, `run_agent_streamed_auto_send`, and `emit_langgraph_messages` are exported from `adk/__init__.py` and may be imported by consumers/tutorials. After Batch E migrates the tutorials, confirm no consumer needs them:

Run: `grep -rn "stream_pydantic_ai_events\|stream_langgraph_events\|run_agent_streamed_auto_send\|emit_langgraph_messages" src/ tests/ examples/`

- [ ] **Step 1:** If a helper is still wanted, fold it into `_<harness>_sync.py` or `_<harness>_turn.py` and keep a thin re-export from `adk/__init__.py` for one release; otherwise remove it (changelog the public-symbol removal — adds to Batch H). Decide per-symbol based on the grep.
- [ ] **Step 2:** `git rm` `_*_async.py` / `_langgraph_messages.py` once their content is folded and references updated. Update `adk/__init__.py` imports + `__all__`.
- [ ] **Step 3: Verify**

Run: `uv run --all-packages --all-extras pytest tests/lib/adk/ tests/lib/core/harness/ -q` → green.
Run: `uv run --all-packages python -c "import agentex.lib.adk; print('ok')"` → `ok`.

### Task I2: Move openai out of `providers/_modules/` into `_modules/`

**Files:**
- `git mv src/agentex/lib/adk/providers/_modules/openai_turn.py src/agentex/lib/adk/_modules/_openai_turn.py`
- Create `src/agentex/lib/adk/_modules/_openai_sync.py` from the sync-delivery pieces of `providers/_modules/sync_provider.py` (and the harness-tap `convert_openai_to_agentex_events`), aligning naming with the other four.
- Decide placement of `providers/_modules/openai.py` (the ~745-line Temporal **activities** provider): if it is a provider-activity module rather than a harness tap, it may stay under `providers/`; the directive is about the harness surface. Confirm with the grep below before moving it.
- Update importers: `adk/__init__.py`, `src/agentex/lib/cli/templates/sync-openai-agents/project/acp.py.j2` (imports `SyncStreamingProvider, convert_openai_to_agentex_events` from `agentex.lib.adk.providers._modules.sync_provider`), and any test.

- [ ] **Step 1: Inventory every openai import path**

Run: `grep -rn "providers._modules.openai\|providers/_modules/openai\|sync_provider\|openai_turn\|SyncStreamingProvider\|convert_openai_to_agentex_events" src/ tests/ examples/`

- [ ] **Step 2: Move + rename** the harness-surface modules into `_modules/_openai_sync.py` / `_openai_turn.py`. Keep `SyncStreamingProvider`/`SyncStreamingModel` (they are the supported sync path) — relocate them into `_openai_sync.py` (or keep a re-export shim at the old path for one release so the CLI template keeps working until updated).
- [ ] **Step 3: Keep a back-compat shim at the old paths — do NOT expect zero references.** Several consumers legitimately import from `providers/_modules/sync_provider.py` and are NOT migrated by this plan: the `sync-openai-agents` CLI template, and the base sync tutorials `examples/tutorials/00_sync/010_multiturn/project/acp.py` (`SyncStreamingProvider`) and `00_sync/020_streaming/project/acp.py` (`SyncStreamingProvider` + `convert_openai_to_agentex_events`). So `sync_provider.py` MUST remain as a shim that keeps `SyncStreamingModel`/`SyncStreamingProvider` and re-exports the relocated `convert_openai_to_agentex_events` from `_modules/_openai_sync.py`; likewise leave a shim at `providers/_modules/openai_turn.py` re-exporting `OpenAITurn`. Update only the internal importers you actually moved (`adk/__init__.py`, the relocated test).
- [ ] **Step 4: (optional) Move the openai turn test** `tests/lib/adk/providers/test_openai_turn.py` → `tests/lib/adk/test_openai_turn.py` for symmetry, or leave it and just repoint its import to the new `_modules/_openai_turn` path (required because it monkeypatches `convert_openai_to_agentex_events` on the turn module's namespace).
- [ ] **Step 5: Verify**

Run: `grep -rn "providers._modules.openai_turn\|providers._modules.sync_provider" src/ tests/ examples/` → the only remaining hits are the kept shims (`providers/_modules/{sync_provider,openai_turn}.py` themselves) and their intended one-release consumers (the `sync-openai-agents` template + the `010_multiturn`/`020_streaming` base sync tutorials). Confirm each resolves via the shim — `python -c "from agentex.lib.adk.providers._modules.sync_provider import SyncStreamingProvider, convert_openai_to_agentex_events"` — NOT that the count is zero.
Run: `uv run --all-packages --all-extras pytest tests/lib/adk/ tests/lib/core/harness/ -q` → green.
Run: `uv run --all-packages python -c "import agentex.lib.adk; print('ok')"` → `ok`.

### Task I3: Normalize test naming (`_sync.py` vs `_sync_unified.py`)

Verified duplicate-ish test files: `tests/lib/adk/test_langgraph_sync.py` + `test_langgraph_sync_unified.py`, and `test_pydantic_ai_sync.py` + `test_pydantic_ai_sync_unified.py`.

- [ ] **Step 1: Diff each pair** to see whether `_unified` is the post-migration replacement of the pre-unified `_sync` test or genuinely separate coverage.
- [ ] **Step 2:** Merge into one `test_<harness>_sync.py` per harness (folding still-relevant cases), or rename consistently. Remove the redundant file.
- [ ] **Step 3: Verify + commit I1–I3 together**

Run: `uv run --all-packages --all-extras pytest tests/lib/adk/ tests/lib/core/harness/ -q` → green.
Run: `uv run ruff check src/ tests/ && uv run pyright src/agentex/lib/adk/__init__.py` → clean.
```bash
git add -A
git commit -m "refactor(harness)!: consolidate harness modules to _<harness>_sync.py + _<harness>_turn.py under _modules/ (openai moved out of providers/_modules)"
```

---

## Batch H — Final docs, changelog, and stale-plan-doc removal

### Task H1: Remove the stale unified-harness plan doc(s)

The pre-unified planning docs for the now-merged stack are obsolete.

**Files:** `git rm docs/superpowers/plans/2026-06-18-unified-harness-surface-pr4-pydantic-ai.md` (and any sibling `*-unified-harness-*` plan doc that lands).

- [ ] **Step 1:** `ls docs/superpowers/plans/` and remove the unified-harness-surface plan doc(s). Keep this PR-10 plan until PR 10 itself merges.
- [ ] **Step 2: Commit** (`docs: remove stale unified-harness-surface planning doc (stack merged)`).

### Task H2: Final docs consistency pass + changelog

- [ ] **Step 1:** Re-read `adk/docs/harness.md` end-to-end against the post-E/F/I tree; confirm every symbol, tap, example, and module path matches reality.
- [ ] **Step 2: Re-grep for any stale reference**

Run: `grep -rln "harness_pydantic_ai\|harness_langgraph\|harness_openai\|harness_codex\|create_.*_tracing_handler" examples/ docs/ adk/docs/ src/agentex/lib/cli/templates/ README.md`
Expected: zero for the `harness_*` paths and the deprecated handlers. (This plan doc itself still names the old `harness_*`/openai dirs as the historical retirement record — that is expected.) Then separately confirm the `sync_provider`/`openai_turn` shims still resolve for their intended one-release consumers (the `sync-openai-agents` template + the `010_multiturn`/`020_streaming` base sync tutorials), rather than expecting zero references — `python -c "from agentex.lib.adk.providers._modules.sync_provider import SyncStreamingProvider, convert_openai_to_agentex_events; from agentex.lib.adk.providers._modules.openai_turn import OpenAITurn"`.

- [ ] **Step 3: Add the changelog / release note** documenting the breaking removals: `create_langgraph_tracing_handler` / `create_pydantic_ai_tracing_handler` (+ classes), any removed `stream_*_events`/`emit_langgraph_messages` public helper, the openai module relocation (new import path), and the `adk.harness` namespace if adopted.
- [ ] **Step 4: Commit** (`docs(harness): final docs consistency pass + changelog for the harness-cleanup removals`).

---

## Verification (whole PR)

- Grep the whole repo (and confirm with the golden agent / known consumers) for each removed symbol — zero references before deletion (Task F1 Step 1, I1/I2 inventories).
- After Batch A: the shared `_fakes` module is the only definition of the fakes; the determinism test exists once — grep confirms no per-file/per-harness copies.
- After Batch B/I: the five harnesses each have exactly `_<harness>_sync.py` + `_<harness>_turn.py` under `adk/_modules/`; openai no longer lives under `providers/_modules/`; the turn modules use the shared usage normalizer. `ls src/agentex/lib/adk/_modules/_*.py` shows the 10 expected files (+ any deliberately-kept shim).
- After Batch E: exactly one tutorial agent per framework per tier; none import deprecated symbols; tutorial CI job + index/README links resolve.
- `adk/docs/harness.md` documents all five taps, uses the canonical `yield_turn` example with no unused variable, and references no deprecated symbol or old module path.
- The `sync-openai-agents` CLI template imports the new openai path and renders/runs.
- Full `./scripts/test` on Python 3.12 AND 3.13. **Run the two versions separately or in shorter scoped batches** — the dual-version `./scripts/test` in one shot has tripped a 600s no-output watchdog; prefer scoped runs or background with periodic output.
- `./scripts/lint` clean (whole-repo ruff + pyright).
- Changelog / release note present (Task H2).

## Risk

Removing publicly-exported (deprecated) symbols and relocating public module paths are breaking changes — gate Batches E/F/I on the version-bump policy and on confirming the golden agent + any external consumers are migrated. The openai relocation touches a live CLI template; keep a one-release re-export shim if any external code may import the old path. Everything here is recoverable from history; sequence it as the final, deliberate cleanup of the harness-surface workstream. Batches A–D and G are non-breaking and can ship earlier if E/F/I are blocked.

---

## Appendix — scope-item → batch mapping (auditable)

| Scope item | Batch/Task |
|---|---|
| 1 — delete deprecated tracing handlers | F1 |
| 2 — remove resolved-workaround markers | F2 |
| 3 — adk.harness namespace (optional) | C2 |
| 4 — vestigial conformance runner | D |
| 5 — dead sync/async branches | B1 / I1 |
| 6 — shared test fakes | A1 |
| 7 — parametrize determinism test | A2 |
| 8 — shared usage normalization | B2 |
| 9 — converge sync paths | B3 / I |
| 10 — reconcile adk/__init__.py edits | C1 |
| 11 — tutorial consistency pass | E1 |
| 12 — integration-test parity | G |
| 13 — retire duplicate tutorials | E1 |
| NEW — filesystem layout + naming (sync.py/turn.py, openai→_modules) | I |
| NEW — remove stale unified-harness plan doc | H1 |

Cross-cutting facts to preserve:
- Items 1 and 13 are coupled — the pre-unified tutorials import the symbols item 1 removes; retire them in the same commit range (Batches E+F).
- Item 11's renames ARE item 13's retirement — one operation, not two.
- Settled tutorial decision: **replace in place on the numbered `NNN_<name>` paradigm**; codex takes fresh `NNN_codex` numbers; `090_claude_agents_sdk_mvp` (Agents SDK, not the claude-code harness) stays.
- The openai `SyncStreamingModel`/`SyncStreamingProvider` are load-bearing (CLI template) — relocate in Batch I with a shim, do NOT delete in Batch F.
- Non-breaking (A–D, G, H1) vs breaking (E, F, I) — split if the version-bump policy blocks the breaking set.
