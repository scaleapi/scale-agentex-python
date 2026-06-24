# Migration Guide — `agentex-client` 0.16.0 / `agentex-sdk` 0.15.0

This release consolidates the LangGraph, Pydantic-AI, and OpenAI Agents harnesses
onto the **unified harness surface** (`UnifiedEmitter` + `SpanDeriver`), introduces
`run_turn` as the single Temporal entry point for OpenAI Agents, renders
hosted/server-side tool calls in the Temporal streaming model, and ships new CLI
init templates.

Most consumers only need to act on **section 1** (removed tracing handlers).
Sections 2–3 only matter if you import private modules. Section 4 lists the new,
opt-in capabilities. Section 5 documents the defect fixes shipped on top of the
release.

---

## 1. Tracing handlers removed (LangGraph + Pydantic-AI) — **action required**

The bespoke tracing callback handlers are **gone** from the public
`agentex.lib.adk` surface:

| Removed | |
|---|---|
| `agentex.lib.adk.create_langgraph_tracing_handler` | + class `AgentexLangGraphTracingHandler` |
| `agentex.lib.adk.create_pydantic_ai_tracing_handler` | + class `AgentexPydanticAITracingHandler` |

Span tracing is now **derived automatically** from the canonical
`StreamTaskMessage*` stream by `UnifiedEmitter`. You no longer construct or pass a
callback handler — you wrap the run in the harness `*Turn` and drive delivery
through the emitter, and spans fall out of the stream.

### LangGraph

**Before**

```python
from agentex.lib import adk

handler = adk.create_langgraph_tracing_handler(
    trace_id=trace_id,
    parent_span_id=parent_span_id,
)
result = await graph.ainvoke(state, config={"callbacks": [handler]})
```

**After**

```python
from agentex.lib.adk import stream_langgraph_events  # facade name unchanged

# Streaming delivery + tracing are handled for you; no callbacks wiring.
async for event in stream_langgraph_events(graph, state, ...):
    ...
```

or, when you own the emitter directly:

```python
from agentex.lib.adk import LangGraphTurn
from agentex.lib.core.harness import UnifiedEmitter

emitter = UnifiedEmitter(...)
await emitter.auto_send_turn(LangGraphTurn(...))   # or: emitter.yield_turn(...)
```

### Pydantic-AI

**Before**

```python
handler = adk.create_pydantic_ai_tracing_handler(trace_id=..., parent_span_id=...)
```

**After**

```python
from agentex.lib.adk import PydanticAITurn, stream_pydantic_ai_events
from agentex.lib.core.harness import UnifiedEmitter

# Wrap in PydanticAITurn and drive UnifiedEmitter.yield_turn / auto_send_turn.
await UnifiedEmitter(...).auto_send_turn(PydanticAITurn(...))
```

The `agentex init` templates were migrated to this pattern. If you scaffolded
from an older template, regenerate (or diff against a fresh template) for the
canonical shape.

---

## 2. Private `_modules` import paths changed — **only if you import privates**

Each harness now exposes exactly `_<harness>_sync.py` + `_<harness>_turn.py` under
`agentex.lib.adk._modules`. Several private modules were deleted and their
functions relocated. If you imported the **public facade names** from
`agentex.lib.adk`, **nothing changes**. Repoint only if you reached into the
private modules directly:

| Old (deleted) private import | New location | Public facade (unchanged) |
|---|---|---|
| `_modules._langgraph_async.stream_langgraph_events` | `_modules._langgraph_turn` | `adk.stream_langgraph_events` |
| `_modules._langgraph_messages.emit_langgraph_messages` | `_modules._langgraph_sync` | `adk.emit_langgraph_messages` |
| `_modules._langgraph_tracing.*` | **removed** (see §1) | — |
| `_modules._pydantic_ai_async.stream_pydantic_ai_events` | `_modules._pydantic_ai_turn` | `adk.stream_pydantic_ai_events` |
| `_modules._pydantic_ai_tracing.*` | **removed** (see §1) | — |

✅ These facade names are unchanged and keep working:
`stream_langgraph_events`, `emit_langgraph_messages`,
`convert_langgraph_to_agentex_events`, `LangGraphTurn`,
`stream_pydantic_ai_events`, `convert_pydantic_ai_to_agentex_events`,
`PydanticAITurn`.

---

## 3. OpenAI harness moved into `adk/_modules` + facade export

The OpenAI Agents harness now lives alongside the others:

- `OpenAITurn`, `openai_usage_to_turn_usage` → `agentex.lib.adk._modules._openai_turn`
- `convert_openai_to_agentex_events` → `agentex.lib.adk._modules._openai_sync`

New **public** facade exports (prefer these):

```python
from agentex.lib.adk import (
    OpenAITurn,
    convert_openai_to_agentex_events,
    openai_usage_to_turn_usage,
)
```

Back-compat shims remain at
`agentex.lib.adk.providers._modules.{openai_turn,sync_provider}` **for one
release** — migrate to the facade names before the next minor.

---

## 4. New capabilities (opt-in, no migration required)

- **`run_turn` — unified Temporal entry point for OpenAI Agents.**

  ```python
  from agentex.lib.core.temporal.plugins.openai_agents import run_turn, OpenAIAgentsTurnResult

  result = await run_turn(
      agent, input,
      task_id=task_id,
      trace_id=trace_id,
      parent_span_id=parent_span_id,
  )
  result.final_output   # raw SDK final_output
  result.usage          # normalized TurnUsage for the turn span
  ```

  It emits each tool call exactly once (the streaming model is the sole
  tool-**request** emitter; hooks emit tool **responses**), traces per-tool spans,
  normalizes token usage, and drains orphaned tool spans in a `finally` block if
  the run terminates mid-tool. Existing `TemporalStreamingHooks` callers keep
  working — `run_turn` is additive. If you pass your own `hooks` subclass, also
  set `emit_tool_requests=False` and forward `trace_id` / `parent_span_id`
  yourself (they are only auto-applied to the default hooks).

- **Hosted / server-side tool rendering** in `TemporalStreamingModel`:
  web_search, file_search, code_interpreter, image_generation, server-side mcp,
  computer, and local_shell calls now surface as ToolRequest/ToolResponse pairs.

- **New CLI init templates:** `default` / `sync` / `temporal` flavors of
  `claude-code` and `codex`, plus `default-openai-agents`.

---

## 5. Defect fixes shipped with this migration

These fixes harden the newly-added sync OpenAI converter
(`convert_openai_to_agentex_events` / `OpenAITurn`) and the Temporal hosted-tool
path. No API change — behavior only.

1. **Malformed tool arguments no longer abort the turn.** The converter now
   parses raw tool-call arguments through a defensive helper
   (`_safe_parse_arguments`): a non-decodable string is preserved under `raw`
   and a non-dict JSON value under `value`, instead of raising `JSONDecodeError`
   and killing the run before later output is delivered. This matches the
   Temporal streaming model's existing fallback.

2. **Reasoning messages are closed.** Completed reasoning content/summary items
   now emit a matching `StreamTaskMessageDone`. Previously the `Done` was
   skipped, so `UnifiedEmitter.auto_send` never released the context and the
   reasoning span could be marked incomplete (reasoning-model output appeared to
   hang).

3. **Text no longer collides with reasoning.** Every new text `item_id` now
   reserves a fresh message index (matching the increment-then-use convention of
   the reasoning/tool paths). Previously the first text item reused the current
   index, so on reasoning-model streams the final answer could overwrite the
   reasoning message, duplicate a `Start`, or route deltas into the wrong context.

4. **Hosted-tool response shape aligned.** Hosted/server-side tool responses in
   `TemporalStreamingModel` now emit `content` as a plain string, matching the
   function-tool response path (`on_tool_end`) so hosted and function tools
   render identically within the same flow.

> Action: if you adopted `OpenAITurn` for **reasoning models** (o1/o3/gpt-5) on
> the sync path before these fixes, upgrade — fixes 2 and 3 are required for
> correct reasoning rendering.
