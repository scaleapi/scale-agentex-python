# Temporal Pydantic AI Harness Test Agent

A minimal **Temporal-backed** Pydantic AI agent that drives the **unified
harness surface** (`UnifiedEmitter.auto_send_turn` + `PydanticAITurn`) from
inside the model activity's `event_stream_handler`.

## Why this agent exists

The `10_async/10_temporal/110_pydantic_ai` tutorial streams via the
`stream_pydantic_ai_events` helper (which uses the unified surface internally).
This harness test agent calls `emitter.auto_send_turn(...)` **explicitly** inside
the `event_stream_handler`, making the unified-surface wiring visible and giving
the temporal channel direct coverage.

## How it wires the unified surface

In `project/agent.py`, the `event_stream_handler` runs inside the model activity
and constructs a `UnifiedEmitter` from `RunContext.deps`:

```python
async def event_handler(run_context, events):
    emitter = UnifiedEmitter(
        task_id=run_context.deps.task_id,
        trace_id=run_context.deps.task_id,
        parent_span_id=run_context.deps.parent_span_id,
    )
    turn = PydanticAITurn(events, model=MODEL_NAME, coalesce_tool_requests=True)
    await emitter.auto_send_turn(turn)
```

- The handler runs inside a Temporal activity, so it can freely make
  non-deterministic Redis + tracing writes.
- `coalesce_tool_requests=True` is required on the auto_send path until
  AGX1-377 lands.
- `deps` (set by `project/workflow.py`) threads the `task_id` and the per-turn
  `parent_span_id` into the handler so tool spans nest under the workflow's turn
  span.

## Structure

- `project/acp.py` — thin ACP server; FastACP auto-wires HTTP routes to the
  workflow when `TemporalACPConfig` is used.
- `project/agent.py` — base `Agent` + `TemporalAgent` + the unified-surface
  `event_stream_handler`.
- `project/workflow.py` — durable workflow; each turn delegates to
  `temporal_agent.run(...)`.
- `project/run_worker.py` — Temporal worker entry point.
- `project/tools.py` — async `get_weather(city)` returning a constant.
- `tests/test_agent.py` — live integration test (requires Temporal + Redis +
  ACP server + worker).

## Tools

- `get_weather(city: str) -> str` (async): returns a fixed "sunny and 72°F"
  string. Each tool call becomes its own Temporal activity.

## Offline coverage

Offline integration tests for the same wiring (pydantic-ai `TestModel` + fake
streaming/tracing, no Temporal server) live in the SDK repo at
`tests/lib/core/harness/test_harness_pydantic_ai_temporal.py`.
