# Unified Harness Surface — PR 4: pydantic-ai Migration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the pydantic-ai harness onto the unified harness surface so it emits streaming + persisted messages + tracing + turn usage through ONE source of truth, over both delivery channels (yield + auto-send), with no public regression — and ship its 3 integration test agents (sync/async/temporal).

**Architecture:** Wrap a pydantic-ai run as a `HarnessTurn` (canonical `StreamTaskMessage*` stream + normalized `TurnUsage`). Reuse the existing `convert_pydantic_ai_to_agentex_events` mapping as the tap. Reimplement the existing public auto-send helper on top of `UnifiedEmitter.auto_send_turn`, and route sync ACP agents through `UnifiedEmitter.yield_turn`. Retire the bespoke `_pydantic_ai_tracing` handler in favor of the surface's derived spans (keep the old symbol as a deprecated shim).

**Tech Stack:** Python 3, pydantic-ai (`pydantic_ai`), pydantic v2, pytest + pytest-asyncio, the `agentex.lib.core.harness` package from PRs 1-3.

**Foundation:** `src/agentex/lib/core/harness/` (`UnifiedEmitter`, `SpanTracer`, `SpanDeriver`, `HarnessTurn`, `TurnUsage`, `TurnResult`, `yield_events`, `auto_send`, conformance scaffold). Design: `docs/superpowers/specs/2026-06-18-unified-harness-surface-design.md`.

---

## Dependencies (must land first)

- **AGX1-373** — cross-channel conformance equivalence + `Full` wire reconciliation. PR 4's conformance fixtures register into the upgraded cross-channel runner. **Do not start Task 6 until 373 is merged into the foundation branch.**
- **AGX1-375** — public `adk` import path for the harness surface. If merged, import the surface via the public path in this PR; if not, import from `agentex.lib.core.harness` and add a follow-up note. (Tasks below assume `from agentex.lib.core.harness import UnifiedEmitter, TurnUsage, ...`; swap to the public path if 375 landed.)

This is one PR (target < 1000 lines code, excluding any recorded fixtures). The 3 test agents are the largest chunk; if the diff exceeds budget, split the test agents into a follow-up PR 4b (note in the PR description).

---

## File Structure

- Modify `src/agentex/lib/adk/_modules/_pydantic_ai_sync.py` — add an optional `on_result` callback to `convert_pydantic_ai_to_agentex_events` (additive) so usage can be captured. Behavior unchanged when omitted.
- Create `src/agentex/lib/adk/_modules/_pydantic_ai_turn.py` — `PydanticAITurn(HarnessTurn)` + `pydantic_ai_usage_to_turn_usage(...)`.
- Modify `src/agentex/lib/adk/_modules/_pydantic_ai_async.py` — reimplement `stream_pydantic_ai_events` on `UnifiedEmitter.auto_send_turn`, preserving signature + return.
- Modify `src/agentex/lib/adk/_modules/_pydantic_ai_tracing.py` — mark `create_pydantic_ai_tracing_handler` / `AgentexPydanticAITracingHandler` deprecated (docstring + `DeprecationWarning`); keep importable.
- Create `tests/lib/core/harness/conformance/test_pydantic_ai_conformance.py` — register pydantic-ai fixtures into the cross-channel conformance runner.
- Create `examples/tutorials/harness-pydantic-ai-{sync,async,temporal}/` — 3 test agents (modeled on the `sync-pydantic-ai` / `default-pydantic-ai` / `temporal-pydantic-ai` CLI templates) using the unified surface.
- Modify `.github/workflows/harness-integration.yml` — enable the pydantic-ai rows of the `live-matrix` job.
- Modify `.github/workflows/agentex-tutorials-test.yml` (or its agent list) — include the 3 new test agents if that workflow enumerates agents.

---

## Task 1: Expose the pydantic-ai run result for usage capture

**Files:**
- Modify: `src/agentex/lib/adk/_modules/_pydantic_ai_sync.py`
- Test: `tests/lib/adk/test_pydantic_ai_sync.py` (create if absent)

The converter already iterates the pydantic-ai event stream and currently *ignores* `AgentRunResultEvent` (the terminal event carrying the run result + usage). Add an optional callback so a caller can capture it without changing existing behavior.

- [ ] **Step 1: Write the failing test.**

```python
import pytest
from agentex.lib.adk._modules._pydantic_ai_sync import convert_pydantic_ai_to_agentex_events


class _FakeResultEvent:  # stand-in for pydantic_ai.run.AgentRunResultEvent
    def __init__(self, result):
        self.result = result


async def _stream(events):
    for e in events:
        yield e


@pytest.mark.asyncio
async def test_on_result_callback_receives_terminal_event(monkeypatch):
    # When the stream ends with an AgentRunResultEvent, on_result is invoked with it,
    # and the converter still yields no extra events for it.
    captured = {}
    # Use a real AgentRunResultEvent if constructable; otherwise patch isinstance check.
    # (Implementer: see Step 3 note — match the real terminal event type.)
    ...
```

Implementer note: the exact terminal event type is `pydantic_ai.run.AgentRunResultEvent` (already imported in `_pydantic_ai_sync.py`). Write the test to feed a stream ending in a real `AgentRunResultEvent` (construct it as the installed pydantic-ai version requires; inspect `python -c "import pydantic_ai.run, inspect; print(inspect.signature(pydantic_ai.run.AgentRunResultEvent))"`). Assert `on_result` is called once with that event and that the converter yields the same `StreamTaskMessage*` sequence as without the callback (no behavior change for the streaming output).

- [ ] **Step 2: Run** `uv run pytest tests/lib/adk/test_pydantic_ai_sync.py -v` — expect FAIL (no `on_result` param).

- [ ] **Step 3: Implement.** Add `on_result: Callable[[AgentRunResultEvent], None] | None = None` (and an async-callable variant if needed) to `convert_pydantic_ai_to_agentex_events`. In the existing `elif isinstance(event, (FunctionToolCallEvent, FinalResultEvent, AgentRunResultEvent))` branch, when the event is an `AgentRunResultEvent` and `on_result` is set, call it (await if it's a coroutine). Keep yielding nothing for it. No other change.

- [ ] **Step 4: Run** the test — expect PASS, plus run the existing `_pydantic_ai_sync` tests if any to confirm no regression.

- [ ] **Step 5: Commit** `feat(pydantic-ai): optional on_result callback to expose run result for usage capture`.

---

## Task 2: Normalize pydantic-ai usage to `TurnUsage`

**Files:**
- Create: `src/agentex/lib/adk/_modules/_pydantic_ai_turn.py`
- Test: `tests/lib/adk/test_pydantic_ai_turn.py`

- [ ] **Step 1: Verify the real usage shape FIRST.** Run `uv run python -c "from pydantic_ai.usage import RunUsage; import inspect; print([f for f in RunUsage.model_fields])"` (the type/name may be `RunUsage` or `Usage` depending on the installed version). Record the exact field names (commonly: `input_tokens`, `output_tokens`, `total_tokens`, `requests`, and a cache/`details` field). The mapping in Step 3 MUST use the real field names.

- [ ] **Step 2: Write the failing test.**

```python
from agentex.lib.adk._modules._pydantic_ai_turn import pydantic_ai_usage_to_turn_usage


def test_usage_normalization_maps_fields():
    # Build a usage object matching the installed pydantic-ai RunUsage shape
    # (see Task 2 Step 1 for the real fields), then assert the mapping.
    usage_obj = ...  # construct RunUsage(input_tokens=10, output_tokens=20, requests=2, ...)
    tu = pydantic_ai_usage_to_turn_usage(usage_obj, model="openai:gpt-4o")
    assert tu.model == "openai:gpt-4o"
    assert tu.input_tokens == 10
    assert tu.output_tokens == 20
    assert tu.num_llm_calls == 2
```

- [ ] **Step 3: Implement** `pydantic_ai_usage_to_turn_usage(usage, model) -> TurnUsage` mapping the verified RunUsage fields onto `TurnUsage` (`input_tokens`, `output_tokens`, `total_tokens`, `cached_input_tokens` if available, `num_llm_calls` ← `requests`). Use `getattr(usage, "<field>", None)` defensively so a version field rename degrades to `None` rather than crashing. Then implement `PydanticAITurn`:

```python
class PydanticAITurn:
    """A pydantic-ai run as a HarnessTurn: canonical event stream + normalized usage."""

    def __init__(self, stream, model: str | None = None):
        self._stream = stream
        self._model = model
        self._usage = TurnUsage(model=model)

    @property
    async def events(self):
        def _capture(result_event):
            run_result = getattr(result_event, "result", None)
            usage_obj = run_result.usage() if run_result is not None else None
            if usage_obj is not None:
                self._usage = pydantic_ai_usage_to_turn_usage(usage_obj, self._model)
        async for ev in convert_pydantic_ai_to_agentex_events(self._stream, on_result=_capture):
            yield ev

    def usage(self) -> TurnUsage:
        return self._usage
```

(Verify `run_result.usage()` is the correct accessor for the installed version; adjust if it's an attribute.)

- [ ] **Step 4: Add a `PydanticAITurn` test** that feeds a small stream ending in an `AgentRunResultEvent` whose `result.usage()` returns a known usage, drives `turn.events` to exhaustion, then asserts `turn.usage()` reflects the normalized values and that `events` yielded the expected `StreamTaskMessage*`. Confirm `usage()` BEFORE exhaustion returns the default (documented single-pass contract).

- [ ] **Step 5: Run** the tests — expect PASS.

- [ ] **Step 6: Commit** `feat(pydantic-ai): PydanticAITurn HarnessTurn + usage normalization`.

---

## Task 3: Reimplement the auto-send helper on the unified surface

**Files:**
- Modify: `src/agentex/lib/adk/_modules/_pydantic_ai_async.py`
- Test: `tests/lib/adk/test_pydantic_ai_async.py`

`stream_pydantic_ai_events(stream, task_id, ...)` currently hand-drives `adk.streaming`. Reimplement it to delegate to `UnifiedEmitter.auto_send_turn(PydanticAITurn(stream, model))`, preserving its signature and return value (the accumulated final text). Feature-add: traces by default.

- [ ] **Step 1: Capture current behavior as a characterization test.** Before changing anything, write a test that runs the CURRENT `stream_pydantic_ai_events` over a fixture stream with a fake `adk.streaming` and records the messages produced (text, tool request/response). This is the backward-compat baseline ("equivalent messages before/after" from the design).

- [ ] **Step 2: Run** it green against the current implementation. Commit the test alone: `test(pydantic-ai): characterize stream_pydantic_ai_events output`.

- [ ] **Step 3: Reimplement** `stream_pydantic_ai_events` to build a `PydanticAITurn` and call `UnifiedEmitter(task_id=task_id, trace_id=<resolved>, parent_span_id=<resolved>, streaming=<injected or None>).auto_send_turn(turn)`, returning `result.final_text`. Resolve `trace_id`/`parent_span_id` the same way the module does today (from the streaming/tracing context vars it already reads). Preserve the exact public signature and return type.

- [ ] **Step 4: Run** the characterization test — it must still pass (same messages). Adjust the test only if AGX1-373 deliberately changed the tool-message wire shape; in that case assert the post-373 shape and note it. Confirm tracing now occurs by default (assert spans via a fake tracer).

- [ ] **Step 5: Commit** `refactor(pydantic-ai): reimplement stream_pydantic_ai_events on UnifiedEmitter (default tracing)`.

---

## Task 4: Route sync ACP delivery through the surface + deprecate the bespoke tracing handler

**Files:**
- Modify: `src/agentex/lib/adk/_modules/_pydantic_ai_tracing.py`
- (Reference) the sync ACP usage pattern in the pydantic-ai docs/templates.

- [ ] **Step 1: Deprecate the bespoke tracing handler.** Add a `DeprecationWarning` (via `warnings.warn(...)`) and a docstring note to `create_pydantic_ai_tracing_handler` / `AgentexPydanticAITracingHandler` stating the unified surface (`UnifiedEmitter`, which derives spans from the canonical stream) supersedes it. Keep the symbols importable and functional (no removal — backward compat).

- [ ] **Step 2: Confirm the sync path.** The sync tap remains `convert_pydantic_ai_to_agentex_events`. Document (in the module docstring of `_pydantic_ai_sync.py`) the recommended sync ACP usage:

```python
turn = PydanticAITurn(agent.run_stream_events(...), model=...)
async for event in emitter.yield_turn(turn):
    yield event
```

No code change beyond the docstring (the sync converter already yields the canonical stream; `yield_turn` adds tracing). Add a test that `emitter.yield_turn(PydanticAITurn(...))` forwards the same events the bare converter would and derives spans.

- [ ] **Step 3: Run** tests; **Commit** `refactor(pydantic-ai): deprecate bespoke tracing handler; document unified sync path`.

---

## Task 5: pydantic-ai cross-channel conformance fixtures

**Files:**
- Create: `tests/lib/core/harness/conformance/test_pydantic_ai_conformance.py`

**Blocked by AGX1-373** (the cross-channel conformance runner). Once 373 is merged into the foundation branch:

- [ ] **Step 1: Record canonical fixtures.** For 3-4 representative pydantic-ai runs (text-only; single tool; reasoning/thinking; multi-step text+tool), capture the `StreamTaskMessage*` sequence the tap produces (run `convert_pydantic_ai_to_agentex_events` over recorded `AgentStreamEvent` inputs, or hand-author the canonical sequences). Store as `Fixture(name=..., events=[...])`.

- [ ] **Step 2: Register** each fixture with the conformance runner and let the cross-channel parametrized test (from AGX1-373) assert yield-vs-auto-send equivalence + span equivalence for each. Register/parametrize within THIS module (per the runner's documented per-module registry semantics).

- [ ] **Step 3: Run** `./scripts/test tests/lib/core/harness/ -v` — all green. **Commit** `test(pydantic-ai): cross-channel conformance fixtures`.

---

## Task 6: Three integration test agents (sync / async / temporal)

**Files:**
- Create: `examples/tutorials/harness-pydantic-ai-sync/` , `…-async/` , `…-temporal/` (each a minimal Agentex agent).
- Modify: `.github/workflows/harness-integration.yml` (enable pydantic-ai `live-matrix` rows).
- Modify: `.github/workflows/agentex-tutorials-test.yml` if it enumerates agents.

Each agent is the smallest agent that exercises one delivery channel through the unified surface with the pydantic-ai harness.

- [ ] **Step 1: Scaffold from the existing templates.** Base each agent on the corresponding CLI template: `sync-pydantic-ai`, `default-pydantic-ai` (async), `temporal-pydantic-ai` (under `src/agentex/lib/cli/templates/`). In each, the message handler builds `PydanticAITurn(agent.run_stream_events(params.content.content), model=...)` and:
  - sync agent: `async for ev in emitter.yield_turn(turn): yield ev`
  - async + temporal agents: `await emitter.auto_send_turn(turn)` (temporal: inside the activity, as the template already structures it).
  Use a tiny pydantic-ai agent with ONE trivial tool so the run exercises text + a tool call + tool response.

- [ ] **Step 2: Write an integration test per agent** that drives it with a fixed prompt and asserts: valid ordered messages (text + tool request + tool response) and a well-formed span tree. Use the repo's existing tutorial-agent test harness pattern (see `agentex-tutorials-test.yml` and how current tutorial agents are tested).

- [ ] **Step 3: Wire CI.** In `.github/workflows/harness-integration.yml`, replace the `if: false` placeholder `live-matrix` job (or add a real matrix) with the pydantic-ai × {sync, async, temporal} entries, each running its agent's integration test. If `agentex-tutorials-test.yml` enumerates agents, add the three there too. `log`/document any agent-type not covered (none expected for pydantic-ai).

- [ ] **Step 4: Run** the integration tests locally (as far as the env allows) and the conformance + unit suites. **Commit** `test(pydantic-ai): sync/async/temporal integration agents + enable CI live-matrix rows`.

---

## Task 7: Full suite, type check, and backward-compat audit

- [ ] **Step 1:** `./scripts/test tests/lib/core/harness/ tests/lib/adk/ -v` — all green on 3.12 + 3.13.
- [ ] **Step 2:** `uv run pyright src/agentex/lib/` (or the harness + pydantic modules) — 0 new errors.
- [ ] **Step 3: Backward-compat audit.** Confirm the public signatures are unchanged: `convert_pydantic_ai_to_agentex_events` (only gained an optional kwarg), `stream_pydantic_ai_events` (same signature + return), `create_pydantic_ai_tracing_handler` (still importable, now warns). Grep the repo + templates for callers and confirm none broke.
- [ ] **Step 4:** If any fix was needed, **Commit** `chore(pydantic-ai): type/back-compat fixes`.

---

## Self-Review checklist (run before opening the PR)

- Every public symbol that existed before still exists with the same signature (additive-only): `convert_pydantic_ai_to_agentex_events`, `stream_pydantic_ai_events`, `create_pydantic_ai_tracing_handler`.
- The auto-send helper returns the same final text as before (characterization test passes, or the post-373 shape is asserted with a note).
- Tracing is now on by default for both channels and is overridable (emitter `tracer=False`).
- Usage normalization uses the REAL pydantic-ai usage field names (verified in Task 2 Step 1), with defensive `getattr`.
- Conformance fixtures register per-module and pass the cross-channel assertion from AGX1-373.
- 3 test agents exist and their CI rows are enabled.
- No `# type: ignore` added without justification.

## Notes for the PR description

- Link AGX1-373 (dependency) and AGX1-375 (import path); note AGX1-374 (reasoning/mixed-ordering auto_send tests) is foundation-level and orthogonal.
- State the diff size; if test agents pushed it over budget, note the PR 4b split.
- This is the template the langgraph (PR 5) and openai (PR 6) migrations follow.
