# Async Pydantic AI Harness Test Agent

A minimal **async** (Redis-streaming) Pydantic AI agent that drives the
**unified harness surface** (`UnifiedEmitter.auto_send_turn` + `PydanticAITurn`)
directly.

## Why this agent exists

The `10_async/00_base/110_pydantic_ai` tutorial streams via the
`stream_pydantic_ai_events` helper (which uses the unified surface internally).
This harness test agent calls `emitter.auto_send_turn(...)` **explicitly** at the
agent-author level, making the unified-surface wiring visible and giving the
async channel direct coverage.

## How it wires the unified surface

In `project/acp.py`:

```python
emitter = UnifiedEmitter(
    task_id=task_id,
    trace_id=task_id,
    parent_span_id=turn_span.id if turn_span else None,
)
async with agent.run_stream_events(user_message, message_history=previous_messages) as stream:
    turn = PydanticAITurn(tee_messages(stream), model=MODEL_NAME, coalesce_tool_requests=True)
    result = await emitter.auto_send_turn(turn)
```

- `coalesce_tool_requests=True` is required on the async/auto_send path until
  AGX1-377 lands: tool requests are delivered as a single `Full(tool_request)`
  rather than streamed `Start + Delta + Done`.
- The `UnifiedEmitter` is constructed from the ACP context (`task_id` +
  `trace_id` + `parent_span_id`) so messages auto-send to the task stream
  (Redis) and tracing is automatic.
- Multi-turn memory is persisted via `adk.state` (pydantic-ai message history
  round-tripped through `ModelMessagesTypeAdapter`).

## Files

- `project/acp.py` — async ACP handler using `emitter.auto_send_turn(...)`.
- `project/agent.py` — builds the `pydantic_ai.Agent` with one tool.
- `project/tools.py` — `get_weather(city)` returning a constant.
- `tests/test_agent.py` — live integration test (requires a running agent).

## Tools

- `get_weather(city: str) -> str`: returns a fixed "sunny and 72°F" string.

## Offline coverage

Offline integration tests for the same wiring (pydantic-ai `TestModel` + fake
streaming/tracing, no network) live in the SDK repo at
`tests/lib/core/harness/test_harness_pydantic_ai_async.py`.
