# Unified Harness Surface

The unified harness surface gives every agent harness (pydantic-ai, LangGraph, OpenAI Agents, and future parsers) a single, shared path to streaming, message persistence, and tracing. The Agentex `StreamTaskMessage*` event stream is the canonical wire format. A harness tap produces that stream once; the shared machinery delivers it and derives spans from it.

All public names are re-exported from `agentex.lib.adk`:

```python
from agentex.lib.adk import (
    UnifiedEmitter,
    SpanTracer,
    TurnUsage,
    TurnResult,
    HarnessTurn,
    StreamTaskMessage,
    OpenSpan,
    CloseSpan,
    SpanSignal,
)
```

The implementation lives at `src/agentex/lib/core/harness/`.

---

## The canonical stream: `StreamTaskMessage`

`StreamTaskMessage` is a union of the four wire-protocol update types:

```
StreamTaskMessageStart  - opens a content slot (text, reasoning, tool request, ...)
StreamTaskMessageDelta  - appends a token/fragment to an open slot
StreamTaskMessageFull   - posts a complete message in one shot (tool response, ...)
StreamTaskMessageDone   - closes an open slot
```

Every harness tap produces a sequence of these. Everything downstream (delivery, tracing) reads the same sequence.

---

## Per-harness taps: `convert_<harness>_to_agentex_events`

A tap is an async generator that translates the harness's native event stream into `StreamTaskMessage*` events. The shipped taps are:

| Harness | Tap function | Exported from |
|---|---|---|
| pydantic-ai | `convert_pydantic_ai_to_agentex_events` | `agentex.lib.adk` |
| LangGraph | `convert_langgraph_to_agentex_events` | `agentex.lib.adk` |
| claude-code | `convert_claude_code_to_agentex_events` | `agentex.lib.adk` |
| codex | `convert_codex_to_agentex_events` | `agentex.lib.adk` |
| OpenAI Agents | `convert_openai_to_agentex_events` | `agentex.lib.adk.providers._modules.sync_provider` |

Each harness also provides a `HarnessTurn` wrapper that pairs its tap's event stream with usage extraction: `PydanticAITurn`, `LangGraphTurn`, `ClaudeCodeTurn`, `CodexTurn`, and `OpenAITurn`.

---

## `HarnessTurn` protocol

`HarnessTurn` is the interface a harness turn object must satisfy to plug into `UnifiedEmitter`:

```python
@runtime_checkable
class HarnessTurn(Protocol):
    @property
    def events(self) -> AsyncIterator[StreamTaskMessage]: ...

    def usage(self) -> TurnUsage: ...
```

`events` is the canonical stream for this turn. `usage()` is valid only after `events` is exhausted (async generators cannot cleanly return a value to the consumer, so usage travels out-of-band).

---

## `TurnUsage`

Token counts and cost for one turn, harness-independent:

```python
class TurnUsage(BaseModel):
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
```

Field names align with `agentex.lib.core.observability.llm_metrics` for easy conversion.

---

## `UnifiedEmitter`

`UnifiedEmitter` ties a turn's canonical stream, tracing context, and delivery mode together. Construct one per turn with the task/trace context from the request:

```python
emitter = UnifiedEmitter(
    task_id=params.task.id,
    trace_id=params.task.id,   # or None to disable tracing
    parent_span_id=turn_span.id if turn_span else None,
)
```

**Tracing is on by default** when `trace_id` is provided. To disable it explicitly, pass `tracer=False`. To inject a custom `SpanTracer` (e.g. in tests), pass it as `tracer=<instance>`.

### Delivery mode 1: `yield_turn` (sync HTTP ACP)

For sync ACP agents that return events directly over the HTTP response:

```python
@acp.on_message_send
async def handle(params):
    turn = MyHarnessTurn(params)          # implements HarnessTurn
    async for event in emitter.yield_turn(turn):
        yield event
```

`yield_turn` forwards each event to the caller and traces spans as a side effect. It is a passthrough when `tracer` is `None`.

### Delivery mode 2: `auto_send_turn` (async/Temporal)

For async or Temporal agents that push to the task stream via Redis:

```python
result: TurnResult = await emitter.auto_send_turn(turn, created_at=workflow.now())
```

`auto_send_turn` drives `adk.streaming` contexts for every message in the stream, derives and records spans, and returns a `TurnResult` with the final text and usage. Pass `created_at` under Temporal to back-date message timestamps deterministically.

---

## `TurnResult`

```python
class TurnResult(BaseModel):
    final_text: str = ""
    usage: TurnUsage = TurnUsage()
```

Returned by `auto_send_turn`. `final_text` is the last text segment of the turn (multi-step runs return only the final segment, matching `stream_langgraph_events` / `stream_pydantic_ai_events` semantics).

---

## Tracing: span derivation

Spans are derived from the canonical stream by `SpanDeriver` (pure, no `adk` dependency) and dispatched to `adk.tracing` by `SpanTracer`. The mapping:

- `StreamTaskMessageStart(ToolRequestContent)` + `StreamTaskMessageDone` on that index -> tool span open (keyed by `tool_call_id`)
- `StreamTaskMessageFull(ToolResponseContent)` whose `tool_call_id` was opened -> tool span close
- `StreamTaskMessageFull(ToolRequestContent)` (harnesses that emit tool calls as Full) -> opens a tool span; matching `Full(ToolResponseContent)` closes it
- `StreamTaskMessageStart(ReasoningContent)` + `StreamTaskMessageDone` -> reasoning span

`SpanTracer` is `SpanDeriver`'s consumer. You can inject a custom `SpanTracer` via `UnifiedEmitter(tracer=<instance>)` for advanced use or testing.

---

## Usage examples by channel

### Sync ACP (`yield_turn`)

Build the harness's `HarnessTurn` wrapper and iterate `emitter.yield_turn(turn)` — the emitter forwards each event to the caller and traces spans as a side effect:

```python
import agentex.lib.adk as adk
from agentex.lib.adk import UnifiedEmitter, ClaudeCodeTurn

@acp.on_message_send
async def handle(params):
    task_id = params.task.id
    async with adk.tracing.span(trace_id=task_id, name="message", ...) as turn_span:
        emitter = UnifiedEmitter(
            task_id=task_id,
            trace_id=task_id,
            parent_span_id=turn_span.id if turn_span else None,
        )
        turn = ClaudeCodeTurn(claude_code_stream)   # any HarnessTurn
        async for event in emitter.yield_turn(turn):
            yield event
```

Every harness follows the same shape — swap `ClaudeCodeTurn` for `PydanticAITurn`, `LangGraphTurn`, `CodexTurn`, or `OpenAITurn` and feed it that harness's native stream.

### Async Temporal (auto-send)

```python
from agentex.lib.adk import UnifiedEmitter

emitter = UnifiedEmitter(
    task_id=task_id,
    trace_id=task_id,
    parent_span_id=parent_span_id,
)
result = await emitter.auto_send_turn(turn, created_at=workflow.now())
# result.final_text — last text segment
# result.usage     — TurnUsage (tokens, cost, ...)
```
