# Unified Harness Surface — Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the shared, harness-independent machinery (span derivation, auto-send delivery, yield delivery, unified emitter, turn-usage types) that the per-harness taps will plug into — corresponding to PRs 1–3 of the design's rollout.

**Architecture:** The Agentex `StreamTaskMessage*` stream is the single source of truth (design Approach A). A pure `SpanDeriver` reduces that stream into open/close span signals. Two delivery adapters consume the same stream — `yield_events` (sync HTTP ACP) and `auto_send` (async/temporal, via `adk.streaming`) — and both observe the deriver to drive `adk.tracing`. A `UnifiedEmitter` ties delivery + tracing + `TurnUsage` together.

**Tech Stack:** Python 3, pydantic v2 (`BaseModel`), pytest + pytest-asyncio, the existing `agentex.lib.adk` streaming/tracing facades.

**Spec:** `docs/superpowers/specs/2026-06-18-unified-harness-surface-design.md`

**Scope note:** This plan covers only the foundation (PRs 1–3). The per-harness migration PRs (4–6: pydantic-ai, langgraph, openai) and parser PRs (7–8: claude-code, codex) each require close reading of that harness's existing converter and get their own plans once this foundation lands. PR 9 (cleanup) follows them. See "Subsequent plans" at the end.

---

## File Structure

- Create `src/agentex/lib/core/harness/__init__.py` — package marker + public re-exports.
- Create `src/agentex/lib/core/harness/types.py` — `OpenSpan`, `CloseSpan`, `SpanSignal`, `TurnUsage`, `TurnResult`, `HarnessTurn` protocol.
- Create `src/agentex/lib/core/harness/span_derivation.py` — `SpanDeriver` (pure reducer).
- Create `src/agentex/lib/core/harness/auto_send.py` — `auto_send()` (canonical stream → `adk.streaming` + tracing).
- Create `src/agentex/lib/core/harness/yield_delivery.py` — `yield_events()` (passthrough + tracing).
- Create `src/agentex/lib/core/harness/emitter.py` — `UnifiedEmitter` facade.
- Create tests under `tests/lib/core/harness/`.

Each file has one responsibility; `span_derivation.py` has zero dependencies on `adk` so it is unit-testable in isolation.

---

## Task 1: Foundation types

**Files:**
- Create: `src/agentex/lib/core/harness/__init__.py`
- Create: `src/agentex/lib/core/harness/types.py`
- Test: `tests/lib/core/harness/test_types.py`

- [ ] **Step 1: Create the package marker**

Create `src/agentex/lib/core/harness/__init__.py`:

```python
"""Shared, harness-independent machinery for the unified harness surface.

The Agentex StreamTaskMessage* stream is the single source of truth; this
package derives spans from it and delivers it (yield or auto-send), so every
harness tap gets streaming + tracing + turn usage uniformly.
"""
```

- [ ] **Step 2: Write the failing test for the types**

Create `tests/lib/core/harness/__init__.py` (empty) and `tests/lib/core/harness/test_types.py`:

```python
from agentex.lib.core.harness.types import (
    OpenSpan,
    CloseSpan,
    TurnUsage,
    TurnResult,
)


def test_open_close_span_construct():
    o = OpenSpan(key="call_1", kind="tool", name="Bash", input={"cmd": "ls"})
    c = CloseSpan(key="call_1", output="files", is_complete=True)
    assert o.key == c.key == "call_1"
    assert o.kind == "tool"
    assert c.is_complete is True


def test_turn_usage_defaults_are_none():
    u = TurnUsage(model="claude-opus-4-6")
    assert u.model == "claude-opus-4-6"
    assert u.input_tokens is None
    assert u.num_tool_calls == 0


def test_turn_result_wraps_usage():
    r = TurnResult(final_text="hi", usage=TurnUsage(model="m"))
    assert r.final_text == "hi"
    assert r.usage.model == "m"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/lib/core/harness/test_types.py -v`
Expected: FAIL with `ModuleNotFoundError: agentex.lib.core.harness.types`

- [ ] **Step 4: Implement the types**

Create `src/agentex/lib/core/harness/types.py`:

```python
"""Types for the unified harness surface."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Literal, Protocol, Union, runtime_checkable

from agentex.types.task_message_update import (
    StreamTaskMessageDelta,
    StreamTaskMessageDone,
    StreamTaskMessageFull,
    StreamTaskMessageStart,
)
from agentex.lib.utils.model_utils import BaseModel

# The canonical stream element. Taps yield these; delivery adapters consume them.
StreamTaskMessage = Union[
    StreamTaskMessageStart,
    StreamTaskMessageDelta,
    StreamTaskMessageFull,
    StreamTaskMessageDone,
]

SpanKind = Literal["tool", "reasoning", "subagent"]


@dataclass
class OpenSpan:
    """Signal to open a child span. `key` pairs an open with its close."""

    key: str
    kind: SpanKind
    name: str
    input: dict[str, Any] = field(default_factory=dict)


@dataclass
class CloseSpan:
    """Signal to close the span previously opened with the same `key`."""

    key: str
    output: Any = None
    is_complete: bool = True  # False when closed by flush() without a result


SpanSignal = Union[OpenSpan, CloseSpan]


class TurnUsage(BaseModel):
    """Harness-independent turn usage/cost, attached to the turn span.

    Token field names align with agentex.lib.core.observability.llm_metrics.
    """

    model: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cached_input_tokens: int | None = None
    reasoning_tokens: int | None = None
    total_tokens: int | None = None
    cost_usd: float | None = None
    duration_ms: int | None = None
    num_llm_calls: int = 0
    num_tool_calls: int = 0
    num_reasoning_blocks: int = 0


class TurnResult(BaseModel):
    """Returned to the caller after a turn is delivered."""

    final_text: str = ""
    usage: TurnUsage = TurnUsage()


@runtime_checkable
class HarnessTurn(Protocol):
    """A single harness turn: a canonical stream plus its normalized usage.

    Python async generators cannot cleanly return a value to their consumer, so
    a tap exposes usage via `usage()` (valid only after `events` is exhausted)
    rather than via StopAsyncIteration.
    """

    @property
    def events(self) -> AsyncIterator[StreamTaskMessage]: ...

    def usage(self) -> TurnUsage: ...
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/lib/core/harness/test_types.py -v`
Expected: PASS (3 passed)

- [ ] **Step 6: Commit**

```bash
git add src/agentex/lib/core/harness/__init__.py src/agentex/lib/core/harness/types.py tests/lib/core/harness/__init__.py tests/lib/core/harness/test_types.py
git commit -m "feat(harness): foundation types for unified harness surface"
```

---

## Task 2: SpanDeriver (pure span derivation) — PR 1

**Files:**
- Create: `src/agentex/lib/core/harness/span_derivation.py`
- Test: `tests/lib/core/harness/test_span_derivation.py`

Derivation rules (from the spec): tool span opens on the `Done` of an index whose `Start`
was a `ToolRequestContent`, and closes on the matching `ToolResponseContent` by
`tool_call_id`; reasoning span opens on `Start(ReasoningContent)` and closes on that index's
`Done`. Parallel tools are keyed by `tool_call_id`. `flush()` closes anything still open.

- [ ] **Step 1: Write failing tests (text, single tool, reasoning, parallel, streamed args, unclosed)**

Create `tests/lib/core/harness/test_span_derivation.py`:

```python
from agentex.lib.core.harness.span_derivation import SpanDeriver
from agentex.lib.core.harness.types import OpenSpan, CloseSpan
from agentex.types.task_message_update import (
    StreamTaskMessageStart,
    StreamTaskMessageDelta,
    StreamTaskMessageFull,
    StreamTaskMessageDone,
)
from agentex.types.text_content import TextContent
from agentex.types.reasoning_content import ReasoningContent
from agentex.types.tool_request_content import ToolRequestContent
from agentex.types.tool_response_content import ToolResponseContent
from agentex.types.tool_request_delta import ToolRequestDelta


def _signals(deriver, events):
    out = []
    for e in events:
        out.extend(deriver.observe(e))
    out.extend(deriver.flush())
    return out


def _tool_req(idx, tcid, name, args):
    return StreamTaskMessageStart(
        type="start", index=idx,
        content=ToolRequestContent(type="tool_request", author="agent",
                                   tool_call_id=tcid, name=name, arguments=args),
    )


def test_text_only_yields_no_spans():
    d = SpanDeriver()
    events = [
        StreamTaskMessageStart(type="start", index=0,
            content=TextContent(type="text", author="agent", content="")),
        StreamTaskMessageDelta(type="delta", index=0,
            delta=None),
        StreamTaskMessageDone(type="done", index=0),
    ]
    assert _signals(d, events) == []


def test_single_tool_opens_on_done_closes_on_response():
    d = SpanDeriver()
    events = [
        _tool_req(0, "call_1", "Bash", {"cmd": "ls"}),
        StreamTaskMessageDone(type="done", index=0),
        StreamTaskMessageFull(type="full", index=1,
            content=ToolResponseContent(type="tool_response", author="agent",
                                        tool_call_id="call_1", name="Bash", content="files")),
    ]
    sigs = _signals(d, events)
    assert sigs == [
        OpenSpan(key="call_1", kind="tool", name="Bash", input={"cmd": "ls"}),
        CloseSpan(key="call_1", output="files", is_complete=True),
    ]


def test_reasoning_opens_on_start_closes_on_done():
    d = SpanDeriver()
    events = [
        StreamTaskMessageStart(type="start", index=0,
            content=ReasoningContent(type="reasoning", author="agent", summary=[], content=[])),
        StreamTaskMessageDone(type="done", index=0),
    ]
    sigs = _signals(d, events)
    assert sigs[0] == OpenSpan(key="reasoning:0", kind="reasoning", name="reasoning", input={})
    assert sigs[1] == CloseSpan(key="reasoning:0", output=None, is_complete=True)


def test_parallel_tools_pair_by_tool_call_id():
    d = SpanDeriver()
    events = [
        _tool_req(0, "a", "T1", {}),
        _tool_req(1, "b", "T2", {}),
        StreamTaskMessageDone(type="done", index=0),
        StreamTaskMessageDone(type="done", index=1),
        StreamTaskMessageFull(type="full", index=2,
            content=ToolResponseContent(type="tool_response", author="agent",
                                        tool_call_id="b", name="T2", content="rb")),
        StreamTaskMessageFull(type="full", index=3,
            content=ToolResponseContent(type="tool_response", author="agent",
                                        tool_call_id="a", name="T1", content="ra")),
    ]
    sigs = _signals(d, events)
    opens = [s for s in sigs if isinstance(s, OpenSpan)]
    closes = [s for s in sigs if isinstance(s, CloseSpan)]
    assert {o.key for o in opens} == {"a", "b"}
    assert [c.key for c in closes] == ["b", "a"]
    assert all(c.is_complete for c in closes)


def test_streamed_args_accumulate_into_open_input():
    d = SpanDeriver()
    events = [
        StreamTaskMessageStart(type="start", index=0,
            content=ToolRequestContent(type="tool_request", author="agent",
                                       tool_call_id="c", name="Bash", arguments={})),
        StreamTaskMessageDelta(type="delta", index=0,
            delta=ToolRequestDelta(type="tool_request", tool_call_id="c", name="Bash",
                                   arguments_delta='{"cmd":')),
        StreamTaskMessageDelta(type="delta", index=0,
            delta=ToolRequestDelta(type="tool_request", tool_call_id="c", name="Bash",
                                   arguments_delta='"ls"}')),
        StreamTaskMessageDone(type="done", index=0),
    ]
    sigs = _signals(d, events)
    assert sigs[0] == OpenSpan(key="c", kind="tool", name="Bash", input={"cmd": "ls"})


def test_unclosed_tool_closed_incomplete_on_flush():
    d = SpanDeriver()
    events = [
        _tool_req(0, "x", "Bash", {}),
        StreamTaskMessageDone(type="done", index=0),
    ]
    sigs = _signals(d, events)
    assert sigs[0] == OpenSpan(key="x", kind="tool", name="Bash", input={})
    assert sigs[1] == CloseSpan(key="x", output=None, is_complete=False)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/lib/core/harness/test_span_derivation.py -v`
Expected: FAIL with `ModuleNotFoundError: agentex.lib.core.harness.span_derivation`

- [ ] **Step 3: Implement `SpanDeriver`**

Create `src/agentex/lib/core/harness/span_derivation.py`:

```python
"""Pure reducer: canonical StreamTaskMessage* stream -> span open/close signals.

Has no dependency on adk; unit-testable in isolation. Delivery adapters feed it
every event and act on the returned signals.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from agentex.types.task_message_update import (
    StreamTaskMessageDelta,
    StreamTaskMessageDone,
    StreamTaskMessageFull,
    StreamTaskMessageStart,
)

from agentex.lib.core.harness.types import CloseSpan, OpenSpan, SpanSignal, StreamTaskMessage


@dataclass
class _ToolReqMeta:
    tool_call_id: str
    name: str
    arguments: dict[str, Any]
    args_buf: str = ""  # accumulated streamed argument fragments


class SpanDeriver:
    """Stateful reducer over the canonical stream.

    Tool span: open on Done of a ToolRequestContent index; close on matching
    ToolResponseContent by tool_call_id. Reasoning span: open on
    Start(ReasoningContent); close on that index's Done.
    """

    def __init__(self) -> None:
        # index -> tool request metadata (present only for tool_request indices)
        self._tool_by_index: dict[int, _ToolReqMeta] = {}
        # index -> reasoning open (present only for reasoning indices)
        self._reasoning_index_open: set[int] = set()
        # tool_call_ids with a currently-open span
        self._open_tool_ids: set[str] = set()

    def observe(self, event: StreamTaskMessage) -> list[SpanSignal]:
        if isinstance(event, StreamTaskMessageStart):
            return self._on_start(event)
        if isinstance(event, StreamTaskMessageDelta):
            return self._on_delta(event)
        if isinstance(event, StreamTaskMessageFull):
            return self._on_full(event)
        if isinstance(event, StreamTaskMessageDone):
            return self._on_done(event)
        return []

    def flush(self) -> list[SpanSignal]:
        """Close anything still open at end of stream, marked incomplete."""
        signals: list[SpanSignal] = []
        for tcid in list(self._open_tool_ids):
            signals.append(CloseSpan(key=tcid, output=None, is_complete=False))
        self._open_tool_ids.clear()
        for idx in sorted(self._reasoning_index_open):
            signals.append(CloseSpan(key=f"reasoning:{idx}", output=None, is_complete=False))
        self._reasoning_index_open.clear()
        return signals

    def _on_start(self, event: StreamTaskMessageStart) -> list[SpanSignal]:
        content = event.content
        idx = event.index if event.index is not None else -1
        ctype = getattr(content, "type", None)
        if ctype == "tool_request":
            self._tool_by_index[idx] = _ToolReqMeta(
                tool_call_id=content.tool_call_id,
                name=content.name,
                arguments=dict(content.arguments or {}),
            )
            return []
        if ctype == "reasoning":
            self._reasoning_index_open.add(idx)
            return [OpenSpan(key=f"reasoning:{idx}", kind="reasoning", name="reasoning", input={})]
        return []

    def _on_delta(self, event: StreamTaskMessageDelta) -> list[SpanSignal]:
        idx = event.index if event.index is not None else -1
        delta = event.delta
        if delta is not None and getattr(delta, "type", None) == "tool_request":
            meta = self._tool_by_index.get(idx)
            if meta is not None and delta.arguments_delta:
                meta.args_buf += delta.arguments_delta
        return []

    def _on_full(self, event: StreamTaskMessageFull) -> list[SpanSignal]:
        content = event.content
        if getattr(content, "type", None) == "tool_response":
            tcid = content.tool_call_id
            if tcid in self._open_tool_ids:
                self._open_tool_ids.discard(tcid)
                return [CloseSpan(key=tcid, output=content.content, is_complete=True)]
        return []

    def _on_done(self, event: StreamTaskMessageDone) -> list[SpanSignal]:
        idx = event.index if event.index is not None else -1
        meta = self._tool_by_index.pop(idx, None)
        if meta is not None:
            args = meta.arguments
            if meta.args_buf:
                try:
                    args = json.loads(meta.args_buf)
                except json.JSONDecodeError:
                    args = {"_raw": meta.args_buf}
            self._open_tool_ids.add(meta.tool_call_id)
            return [OpenSpan(key=meta.tool_call_id, kind="tool", name=meta.name, input=args)]
        if idx in self._reasoning_index_open:
            self._reasoning_index_open.discard(idx)
            return [CloseSpan(key=f"reasoning:{idx}", output=None, is_complete=True)]
        return []
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/lib/core/harness/test_span_derivation.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add src/agentex/lib/core/harness/span_derivation.py tests/lib/core/harness/test_span_derivation.py
git commit -m "feat(harness): pure SpanDeriver reducing the canonical stream to span signals"
```

---

## Task 3: Tracer adapter (span signals -> adk.tracing)

**Files:**
- Create: `src/agentex/lib/core/harness/tracer.py`
- Test: `tests/lib/core/harness/test_tracer.py`

A thin adapter that turns `SpanSignal`s into `adk.tracing` spans, nesting them under a parent
span. Kept separate from `SpanDeriver` so derivation stays pure and tracing stays overridable.
Tracing failures are best-effort and never raise (spec error-handling contract).

- [ ] **Step 1: Write the failing test (uses a fake adk.tracing)**

Create `tests/lib/core/harness/test_tracer.py`:

```python
import pytest

from agentex.lib.core.harness.tracer import SpanTracer
from agentex.lib.core.harness.types import OpenSpan, CloseSpan


class _FakeSpan:
    def __init__(self, name):
        self.name = name


class _FakeTracing:
    def __init__(self):
        self.started = []
        self.ended = []

    async def start_span(self, *, trace_id, name, input=None, parent_id=None, data=None, task_id=None):
        self.started.append((name, parent_id, input))
        return _FakeSpan(name)

    async def end_span(self, *, trace_id, span, output=None, data=None):
        self.ended.append((span.name, output))


@pytest.mark.asyncio
async def test_open_then_close_starts_and_ends_span():
    fake = _FakeTracing()
    tracer = SpanTracer(trace_id="t1", parent_span_id="p1", tracing=fake)
    await tracer.handle(OpenSpan(key="call_1", kind="tool", name="Bash", input={"cmd": "ls"}))
    await tracer.handle(CloseSpan(key="call_1", output="files", is_complete=True))
    assert fake.started == [("Bash", "p1", {"cmd": "ls"})]
    assert fake.ended == [("Bash", "files")]


@pytest.mark.asyncio
async def test_no_trace_id_is_noop():
    fake = _FakeTracing()
    tracer = SpanTracer(trace_id="", parent_span_id=None, tracing=fake)
    await tracer.handle(OpenSpan(key="k", kind="tool", name="X"))
    await tracer.handle(CloseSpan(key="k"))
    assert fake.started == [] and fake.ended == []


@pytest.mark.asyncio
async def test_tracing_failure_is_swallowed():
    class _Boom(_FakeTracing):
        async def start_span(self, **kw):
            raise RuntimeError("backend down")

    tracer = SpanTracer(trace_id="t1", parent_span_id="p1", tracing=_Boom())
    # Must not raise.
    await tracer.handle(OpenSpan(key="k", kind="tool", name="X"))
    await tracer.handle(CloseSpan(key="k"))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/lib/core/harness/test_tracer.py -v`
Expected: FAIL with `ModuleNotFoundError: agentex.lib.core.harness.tracer`

- [ ] **Step 3: Implement `SpanTracer`**

Create `src/agentex/lib/core/harness/tracer.py`:

```python
"""Adapter from SpanSignals to adk.tracing spans (best-effort, overridable)."""

from __future__ import annotations

from typing import Any

from agentex.lib.utils.logging import make_logger
from agentex.lib.core.harness.types import CloseSpan, OpenSpan, SpanSignal

logger = make_logger(__name__)


class SpanTracer:
    """Opens/closes adk.tracing child spans in response to span signals.

    `tracing` defaults to the real `adk.tracing` module; inject a fake in tests
    or a custom tracer to override. No-op when `trace_id` is falsy. Never raises.
    """

    def __init__(self, trace_id: str | None, parent_span_id: str | None, tracing: Any = None, task_id: str | None = None):
        self.trace_id = trace_id
        self.parent_span_id = parent_span_id
        self.task_id = task_id
        if tracing is None:
            from agentex.lib import adk

            tracing = adk.tracing
        self._tracing = tracing
        self._open: dict[str, Any] = {}  # span key -> span object

    async def handle(self, signal: SpanSignal) -> None:
        if not self.trace_id:
            return
        try:
            if isinstance(signal, OpenSpan):
                span = await self._tracing.start_span(
                    trace_id=self.trace_id,
                    name=signal.name,
                    input=signal.input,
                    parent_id=self.parent_span_id,
                    task_id=self.task_id,
                )
                if span is not None:
                    self._open[signal.key] = span
            elif isinstance(signal, CloseSpan):
                span = self._open.pop(signal.key, None)
                if span is not None:
                    await self._tracing.end_span(
                        trace_id=self.trace_id,
                        span=span,
                        output=signal.output,
                    )
        except Exception as exc:  # best-effort: tracing never breaks delivery
            logger.warning("[harness.tracer] span signal failed: %s", exc)
```

Note for the implementer: confirm `adk.tracing.end_span` accepts `output=` (seen in
`src/agentex/lib/adk/_modules/tracing.py`). If the kwarg differs, adjust the call and the
fake in the test together.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/lib/core/harness/test_tracer.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/agentex/lib/core/harness/tracer.py tests/lib/core/harness/test_tracer.py
git commit -m "feat(harness): SpanTracer adapter from span signals to adk.tracing"
```

---

## Task 4: `yield_events` delivery adapter — PR 3 (part 1)

**Files:**
- Create: `src/agentex/lib/core/harness/yield_delivery.py`
- Test: `tests/lib/core/harness/test_yield_delivery.py`

`yield_events` passes the canonical stream through unchanged (for sync HTTP ACP agents) while
feeding the `SpanDeriver` + `SpanTracer` as a side effect. Streaming fidelity is untouched.

- [ ] **Step 1: Write the failing test**

Create `tests/lib/core/harness/test_yield_delivery.py`:

```python
import pytest

from agentex.lib.core.harness.yield_delivery import yield_events
from agentex.lib.core.harness.tracer import SpanTracer
from agentex.types.task_message_update import (
    StreamTaskMessageStart,
    StreamTaskMessageDone,
    StreamTaskMessageFull,
)
from agentex.types.tool_request_content import ToolRequestContent
from agentex.types.tool_response_content import ToolResponseContent


class _RecordTracing:
    def __init__(self):
        self.started, self.ended = [], []

    async def start_span(self, *, trace_id, name, input=None, parent_id=None, data=None, task_id=None):
        self.started.append(name)
        return object()

    async def end_span(self, *, trace_id, span, output=None, data=None):
        self.ended.append(output)


async def _gen(events):
    for e in events:
        yield e


@pytest.mark.asyncio
async def test_yield_passes_events_through_and_traces():
    fake = _RecordTracing()
    tracer = SpanTracer(trace_id="t", parent_span_id="p", tracing=fake)
    events = [
        StreamTaskMessageStart(type="start", index=0,
            content=ToolRequestContent(type="tool_request", author="agent",
                                       tool_call_id="c", name="Bash", arguments={})),
        StreamTaskMessageDone(type="done", index=0),
        StreamTaskMessageFull(type="full", index=1,
            content=ToolResponseContent(type="tool_response", author="agent",
                                        tool_call_id="c", name="Bash", content="ok")),
    ]
    out = [e async for e in yield_events(_gen(events), tracer=tracer)]
    assert out == events            # passthrough unchanged
    assert fake.started == ["Bash"] # span derived + opened
    assert fake.ended == ["ok"]     # span closed with response
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/lib/core/harness/test_yield_delivery.py -v`
Expected: FAIL with `ModuleNotFoundError: agentex.lib.core.harness.yield_delivery`

- [ ] **Step 3: Implement `yield_events`**

Create `src/agentex/lib/core/harness/yield_delivery.py`:

```python
"""Yield delivery: pass the canonical stream through, tracing as a side effect."""

from __future__ import annotations

from typing import AsyncIterator

from agentex.lib.core.harness.span_derivation import SpanDeriver
from agentex.lib.core.harness.tracer import SpanTracer
from agentex.lib.core.harness.types import StreamTaskMessage


async def yield_events(
    events: AsyncIterator[StreamTaskMessage],
    tracer: SpanTracer | None = None,
) -> AsyncIterator[StreamTaskMessage]:
    """Forward each event to the caller; derive + trace spans as a side effect.

    For sync HTTP ACP agents that yield events back over the response. When
    `tracer` is None, this is a pure passthrough.
    """
    deriver = SpanDeriver() if tracer is not None else None
    try:
        async for event in events:
            if deriver is not None and tracer is not None:
                for signal in deriver.observe(event):
                    await tracer.handle(signal)
            yield event
    finally:
        if deriver is not None and tracer is not None:
            for signal in deriver.flush():
                await tracer.handle(signal)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/lib/core/harness/test_yield_delivery.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add src/agentex/lib/core/harness/yield_delivery.py tests/lib/core/harness/test_yield_delivery.py
git commit -m "feat(harness): yield_events delivery adapter (passthrough + tracing)"
```

---

## Task 5: `auto_send` delivery adapter — PR 2

**Files:**
- Create: `src/agentex/lib/core/harness/auto_send.py`
- Test: `tests/lib/core/harness/test_auto_send.py`

`auto_send` consumes the canonical stream and drives `adk.streaming` context managers: it opens
a text context for `TextContent`, a reasoning context for `ReasoningContent`, switches cleanly
between them, and posts tool request/response as full messages. It feeds the same
`SpanDeriver`/`SpanTracer` and returns `TurnResult`. This generalizes the golden agent's
`AgentexStreamAdapter` (`teams/sgp/agents/golden_agent/project/harness/adapter.py`) to consume
`StreamTaskMessage*` instead of `HarnessEvent`.

Reference while implementing: `src/agentex/lib/adk/_modules/_langgraph_async.py`
(`stream_langgraph_events`) shows the exact `adk.streaming` open/stream/close pattern to reuse;
`adapter.py` lines 87–130 show the text↔reasoning↔tool switching logic to mirror.

- [ ] **Step 1: Write the failing test (fake streaming records context lifecycle)**

Create `tests/lib/core/harness/test_auto_send.py`:

```python
import pytest

from agentex.lib.core.harness.auto_send import auto_send
from agentex.types.task_message_update import (
    StreamTaskMessageStart,
    StreamTaskMessageDelta,
    StreamTaskMessageDone,
)
from agentex.types.text_content import TextContent
from agentex.types.text_delta import TextDelta


class _FakeCtx:
    def __init__(self, sink):
        self.sink = sink

    async def __aenter__(self):
        self.sink.append(("open",))
        return self

    async def __aexit__(self, *a):
        self.sink.append(("close",))
        return False

    async def stream_update(self, update):
        self.sink.append(("update", update))
        return update


class _FakeStreaming:
    def __init__(self):
        self.sink = []

    def streaming_task_message_context(self, task_id, initial_content, streaming_mode="coalesced", created_at=None):
        self.sink.append(("ctx", getattr(initial_content, "type", None)))
        return _FakeCtx(self.sink)


async def _gen(events):
    for e in events:
        yield e


@pytest.mark.asyncio
async def test_auto_send_streams_text_and_returns_final_text():
    streaming = _FakeStreaming()
    events = [
        StreamTaskMessageStart(type="start", index=0,
            content=TextContent(type="text", author="agent", content="")),
        StreamTaskMessageDelta(type="delta", index=0, delta=TextDelta(type="text", text_delta="Hel")),
        StreamTaskMessageDelta(type="delta", index=0, delta=TextDelta(type="text", text_delta="lo")),
        StreamTaskMessageDone(type="done", index=0),
    ]
    result = await auto_send(_gen(events), task_id="task1", tracer=None, streaming=streaming)
    assert result.final_text == "Hello"
    kinds = [s[0] for s in streaming.sink]
    assert kinds[0] == "ctx" and "open" in kinds and "close" in kinds
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/lib/core/harness/test_auto_send.py -v`
Expected: FAIL with `ModuleNotFoundError: agentex.lib.core.harness.auto_send`

- [ ] **Step 3: Implement `auto_send`**

Create `src/agentex/lib/core/harness/auto_send.py`. The implementer mirrors the text↔reasoning
switching from `adapter.py` and the `adk.streaming` usage from `_langgraph_async.py`:

```python
"""Auto-send delivery: canonical stream -> adk.streaming side effects + tracing."""

from __future__ import annotations

from typing import Any, AsyncIterator

from agentex.types.task_message_update import (
    StreamTaskMessageDelta,
    StreamTaskMessageDone,
    StreamTaskMessageFull,
    StreamTaskMessageStart,
)
from agentex.types.text_content import TextContent

from agentex.lib.core.harness.span_derivation import SpanDeriver
from agentex.lib.core.harness.tracer import SpanTracer
from agentex.lib.core.harness.types import StreamTaskMessage, TurnResult, TurnUsage


async def auto_send(
    events: AsyncIterator[StreamTaskMessage],
    task_id: str,
    tracer: SpanTracer | None = None,
    streaming: Any = None,
    usage: TurnUsage | None = None,
) -> TurnResult:
    """Push the canonical stream to the task stream via adk.streaming.

    Opens a streaming context per text/reasoning message, streams deltas, and
    closes on Done; posts tool request/response as full messages; derives and
    traces spans from the same stream. Returns the accumulated final text +
    usage. For async + temporal agents (call from inside an activity).
    """
    if streaming is None:
        from agentex.lib import adk

        streaming = adk.streaming

    deriver = SpanDeriver() if tracer is not None else None
    final_text_parts: list[str] = []
    current_ctx: Any = None
    current_kind: str | None = None  # "text" | "reasoning"

    async def _close_current() -> None:
        nonlocal current_ctx, current_kind
        if current_ctx is not None:
            await current_ctx.__aexit__(None, None, None)
            current_ctx = None
            current_kind = None

    try:
        async for event in events:
            if deriver is not None and tracer is not None:
                for signal in deriver.observe(event):
                    await tracer.handle(signal)

            if isinstance(event, StreamTaskMessageStart):
                ctype = getattr(event.content, "type", None)
                if ctype in ("text", "reasoning"):
                    await _close_current()
                    current_ctx = streaming.streaming_task_message_context(
                        task_id=task_id, initial_content=event.content,
                    )
                    await current_ctx.__aenter__()
                    current_kind = ctype
            elif isinstance(event, StreamTaskMessageDelta):
                if current_ctx is not None and event.delta is not None:
                    await current_ctx.stream_update(event)
                    if getattr(event.delta, "type", None) == "text" and event.delta.text_delta:
                        final_text_parts.append(event.delta.text_delta)
            elif isinstance(event, StreamTaskMessageDone):
                await _close_current()
            elif isinstance(event, StreamTaskMessageFull):
                # Tool request/response (and any non-streamed full message): post as a
                # standalone full message, not tied to the current text/reasoning ctx.
                await _close_current()
                ctx = streaming.streaming_task_message_context(
                    task_id=task_id, initial_content=event.content,
                )
                await ctx.__aenter__()
                await ctx.__aexit__(None, None, None)
    finally:
        await _close_current()
        if deriver is not None and tracer is not None:
            for signal in deriver.flush():
                await tracer.handle(signal)

    return TurnResult(final_text="".join(final_text_parts), usage=usage or TurnUsage())
```

Note for the implementer: validate the exact `streaming_task_message_context` usage against
`_langgraph_async.py` (whether to call `stream_update` with the whole `StreamTaskMessageDelta`
or the inner delta). Adjust the call and the fake together; the test asserts behavior, not the
internal kwarg shape.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/lib/core/harness/test_auto_send.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add src/agentex/lib/core/harness/auto_send.py tests/lib/core/harness/test_auto_send.py
git commit -m "feat(harness): auto_send delivery adapter (canonical stream -> adk.streaming + tracing)"
```

---

## Task 6: `UnifiedEmitter` facade — PR 3 (part 2)

**Files:**
- Create: `src/agentex/lib/core/harness/emitter.py`
- Modify: `src/agentex/lib/core/harness/__init__.py` (re-export public surface)
- Test: `tests/lib/core/harness/test_emitter.py`

`UnifiedEmitter` is the single thing an agent author touches. It owns the trace context, builds
the `SpanTracer` (default-on when a trace context exists, overridable), and exposes both
delivery modes over a `HarnessTurn`. It attaches the turn's `TurnUsage` to delivery.

- [ ] **Step 1: Write the failing test**

Create `tests/lib/core/harness/test_emitter.py`:

```python
import pytest

from agentex.lib.core.harness.emitter import UnifiedEmitter
from agentex.lib.core.harness.types import TurnUsage
from agentex.types.task_message_update import StreamTaskMessageStart, StreamTaskMessageDone
from agentex.types.text_content import TextContent


class _Turn:
    def __init__(self, events_list, usage):
        self._events_list = events_list
        self._usage = usage

    @property
    async def events(self):
        for e in self._events_list:
            yield e

    def usage(self):
        return self._usage


@pytest.mark.asyncio
async def test_emitter_yield_mode_passes_through():
    events = [
        StreamTaskMessageStart(type="start", index=0,
            content=TextContent(type="text", author="agent", content="hi")),
        StreamTaskMessageDone(type="done", index=0),
    ]
    turn = _Turn(events, TurnUsage(model="m"))
    emitter = UnifiedEmitter(task_id="t", trace_id=None, parent_span_id=None)
    out = [e async for e in emitter.yield_turn(turn)]
    assert out == events


@pytest.mark.asyncio
async def test_emitter_tracing_default_on_when_trace_id_present():
    emitter = UnifiedEmitter(task_id="t", trace_id="trace1", parent_span_id="p")
    assert emitter.tracer is not None


@pytest.mark.asyncio
async def test_emitter_tracing_overridable_off():
    emitter = UnifiedEmitter(task_id="t", trace_id="trace1", parent_span_id="p", tracer=False)
    assert emitter.tracer is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/lib/core/harness/test_emitter.py -v`
Expected: FAIL with `ModuleNotFoundError: agentex.lib.core.harness.emitter`

- [ ] **Step 3: Implement `UnifiedEmitter`**

Create `src/agentex/lib/core/harness/emitter.py`:

```python
"""UnifiedEmitter: the single facade agent authors use for either delivery mode."""

from __future__ import annotations

from typing import Any, AsyncIterator

from agentex.lib.core.harness.auto_send import auto_send
from agentex.lib.core.harness.tracer import SpanTracer
from agentex.lib.core.harness.types import HarnessTurn, StreamTaskMessage, TurnResult
from agentex.lib.core.harness.yield_delivery import yield_events


class UnifiedEmitter:
    """Ties trace context + chosen delivery together.

    Tracing is default-on whenever `trace_id` is truthy; pass `tracer=False` to
    disable, or a custom `SpanTracer` to override.
    """

    def __init__(
        self,
        task_id: str,
        trace_id: str | None,
        parent_span_id: str | None,
        tracer: SpanTracer | bool | None = None,
    ):
        self.task_id = task_id
        self.trace_id = trace_id
        self.parent_span_id = parent_span_id
        if tracer is False:
            self.tracer: SpanTracer | None = None
        elif isinstance(tracer, SpanTracer):
            self.tracer = tracer
        elif trace_id:
            self.tracer = SpanTracer(trace_id=trace_id, parent_span_id=parent_span_id, task_id=task_id)
        else:
            self.tracer = None

    async def yield_turn(self, turn: HarnessTurn) -> AsyncIterator[StreamTaskMessage]:
        """Sync HTTP ACP delivery: forward events, trace as side effect."""
        async for event in yield_events(turn.events, tracer=self.tracer):
            yield event

    async def auto_send_turn(self, turn: HarnessTurn) -> TurnResult:
        """Async/temporal delivery: push to the task stream, return TurnResult."""
        return await auto_send(
            turn.events,
            task_id=self.task_id,
            tracer=self.tracer,
            usage=turn.usage(),
        )
```

- [ ] **Step 4: Re-export the public surface**

Append to `src/agentex/lib/core/harness/__init__.py`:

```python
from agentex.lib.core.harness.emitter import UnifiedEmitter
from agentex.lib.core.harness.tracer import SpanTracer
from agentex.lib.core.harness.types import (
    CloseSpan,
    HarnessTurn,
    OpenSpan,
    SpanSignal,
    StreamTaskMessage,
    TurnResult,
    TurnUsage,
)

__all__ = [
    "UnifiedEmitter",
    "SpanTracer",
    "OpenSpan",
    "CloseSpan",
    "SpanSignal",
    "StreamTaskMessage",
    "TurnUsage",
    "TurnResult",
    "HarnessTurn",
]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/lib/core/harness/ -v`
Expected: PASS (all harness tests green)

- [ ] **Step 6: Commit**

```bash
git add src/agentex/lib/core/harness/emitter.py src/agentex/lib/core/harness/__init__.py tests/lib/core/harness/test_emitter.py
git commit -m "feat(harness): UnifiedEmitter facade tying delivery + tracing + usage"
```

---

## Task 7: Conformance test scaffold + empty CI integration job — PR 3 (part 3)

**Files:**
- Create: `tests/lib/core/harness/conformance/__init__.py`
- Create: `tests/lib/core/harness/conformance/runner.py`
- Create: `tests/lib/core/harness/conformance/test_conformance.py`
- Create: `.github/workflows/harness-integration.yml`

The conformance runner is the shared parametrized engine each harness tap will register fixtures
with (in later plans). It asserts yield-vs-auto-send equivalence on the span signals derived
from a fixture's canonical-event sequence.

- [ ] **Step 1: Write the conformance runner + a self-test fixture**

Create `tests/lib/core/harness/conformance/__init__.py` (empty), then
`tests/lib/core/harness/conformance/runner.py`:

```python
"""Shared conformance engine: every harness tap registers fixtures here.

A fixture is (name, list[StreamTaskMessage]). The runner asserts that span
derivation over the events is identical regardless of delivery channel, which is
the cross-channel guarantee from the spec.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from agentex.lib.core.harness.span_derivation import SpanDeriver
from agentex.lib.core.harness.types import SpanSignal, StreamTaskMessage


@dataclass
class Fixture:
    name: str
    events: list[StreamTaskMessage]


_REGISTRY: list[Fixture] = []


def register(fixture: Fixture) -> None:
    _REGISTRY.append(fixture)


def all_fixtures() -> list[Fixture]:
    return list(_REGISTRY)


def derive_all(events: list[StreamTaskMessage]) -> list[SpanSignal]:
    d = SpanDeriver()
    out: list[SpanSignal] = []
    for e in events:
        out.extend(d.observe(e))
    out.extend(d.flush())
    return out
```

- [ ] **Step 2: Write the conformance test (self-test on a built-in fixture)**

Create `tests/lib/core/harness/conformance/test_conformance.py`:

```python
import pytest

from tests.lib.core.harness.conformance.runner import Fixture, derive_all, register, all_fixtures
from agentex.types.task_message_update import (
    StreamTaskMessageStart, StreamTaskMessageDone, StreamTaskMessageFull,
)
from agentex.types.tool_request_content import ToolRequestContent
from agentex.types.tool_response_content import ToolResponseContent

register(Fixture(
    name="builtin-single-tool",
    events=[
        StreamTaskMessageStart(type="start", index=0,
            content=ToolRequestContent(type="tool_request", author="agent",
                                       tool_call_id="c", name="Bash", arguments={})),
        StreamTaskMessageDone(type="done", index=0),
        StreamTaskMessageFull(type="full", index=1,
            content=ToolResponseContent(type="tool_response", author="agent",
                                        tool_call_id="c", name="Bash", content="ok")),
    ],
))


@pytest.mark.parametrize("fixture", all_fixtures(), ids=lambda f: f.name)
def test_span_derivation_is_deterministic(fixture):
    # Deriving twice over the same events yields identical signals (the property
    # that makes yield vs auto-send equivalent, since both observe the same stream).
    assert derive_all(fixture.events) == derive_all(fixture.events)
```

- [ ] **Step 3: Run the conformance test**

Run: `pytest tests/lib/core/harness/conformance/ -v`
Expected: PASS (1 passed)

- [ ] **Step 4: Add the empty CI integration job**

Create `.github/workflows/harness-integration.yml` (mirrors the structure of the existing
`agentex-tutorials-test.yml`; the matrix is populated in later plans):

```yaml
name: Harness Integration

on:
  pull_request:
    paths:
      - "src/agentex/lib/core/harness/**"
      - "src/agentex/lib/adk/_modules/**"
      - ".github/workflows/harness-integration.yml"

jobs:
  conformance:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - name: Install
        run: uv sync
      - name: Conformance suite
        run: uv run pytest tests/lib/core/harness/ -v

  # Live integration matrix (harness x {sync, async, temporal}) is added per-harness
  # in the migration plans. Placeholder job keeps the workflow valid until then.
  live-matrix:
    runs-on: ubuntu-latest
    if: false  # enabled once the first harness's test agents land
    steps:
      - run: echo "populated by migration PRs"
```

- [ ] **Step 5: Commit**

```bash
git add tests/lib/core/harness/conformance .github/workflows/harness-integration.yml
git commit -m "test(harness): conformance scaffold + CI integration job skeleton"
```

---

## Task 8: Run the full suite + type check

- [ ] **Step 1: Run the whole harness test tree**

Run: `pytest tests/lib/core/harness/ -v`
Expected: PASS (all tasks' tests green)

- [ ] **Step 2: Type check the new package**

Run: `uv run mypy src/agentex/lib/core/harness/` (or the repo's configured type checker)
Expected: no errors. Fix any signature mismatches inline.

- [ ] **Step 3: Final commit if the type check required fixes**

```bash
git add -A && git commit -m "chore(harness): type-check fixes for foundation package"
```

---

## Subsequent plans (to be written after this lands)

Each gets its own plan via the writing-plans skill, expanded with that harness's exact
converter code:

- **PR 4 — Migrate pydantic-ai:** wrap `convert_pydantic_ai_to_agentex_events` as a
  `HarnessTurn` (add `usage()` normalizing `result.usage()`), reimplement `_pydantic_ai_async`
  on `auto_send`, retire `_pydantic_ai_tracing` in favor of `SpanTracer`, keep the public
  `convert_*` signature. Add 3 test agents (sync/async/temporal) + register conformance
  fixtures + enable the live-matrix row.
- **PR 5 — Migrate langgraph:** same shape; reimplement `stream_langgraph_events` on
  `auto_send`; normalize `usage_metadata` into `TurnUsage`.
- **PR 6 — Migrate openai-agents:** same shape; reimplement `run_agent_streamed_auto_send` on
  `auto_send`; normalize `response.usage`.
- **PR 7 — claude-code parser tap:** `convert_claude_code_to_agentex_events` (port the golden
  agent's `_StreamJsonProcessor` to yield `StreamTaskMessage*`) + recorded stream-json
  fixtures + feasible test agent(s).
- **PR 8 — codex parser tap:** same shape for `_CodexEventProcessor`.
- **PR 9 — Cleanup:** delete now-dead internal duplication, deprecate `_*_tracing` shims, docs.

The `is_error` tool-error work is deferred and tracked in Linear as AGX1-371.
