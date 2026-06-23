# Sync Pydantic AI Harness Test Agent

A minimal **synchronous** Pydantic AI agent that drives the **unified harness
surface** (`UnifiedEmitter.yield_turn` + `PydanticAITurn`) on the sync
(HTTP-yield) channel.

## Why this agent exists

The `00_sync/040_pydantic_ai` tutorial streams via the bare
`convert_pydantic_ai_to_agentex_events` converter and does **not** exercise the
unified `yield_turn` path. This harness test agent is the sync coverage for the
unified surface: it proves an agent author can wire the sync channel through
`UnifiedEmitter` and get automatic span derivation (tool spans nested under the
per-turn span) for free, exactly like the async/temporal channels.

## How it wires the unified surface

In `project/acp.py`:

```python
emitter = UnifiedEmitter(
    task_id=task_id,
    trace_id=task_id,
    parent_span_id=turn_span.id if turn_span else None,
)
async with agent.run_stream_events(user_message) as stream:
    turn = PydanticAITurn(stream, model=MODEL_NAME)  # coalesce off: stream tool-call arg tokens
    async for ev in emitter.yield_turn(turn):
        yield ev
```

- `coalesce_tool_requests=False` (the default) preserves token-by-token
  tool-call argument streaming on the sync channel.
- The `UnifiedEmitter` is constructed from the ACP/streaming context
  (`task_id` + `trace_id` + `parent_span_id`) so tool spans nest under the
  per-turn `AGENT_WORKFLOW` span automatically.

## Files

- `project/acp.py` — sync ACP handler using `emitter.yield_turn(...)`.
- `project/agent.py` — builds the `pydantic_ai.Agent` with one tool.
- `project/tools.py` — `get_weather(city)` returning a constant.
- `tests/test_agent.py` — live integration test (requires a running agent).

## Tools

- `get_weather(city: str) -> str`: returns a fixed "sunny and 72°F" string so a
  run deterministically exercises text + a tool call + a tool response.

## Offline coverage

Offline integration tests for the same wiring (pydantic-ai `TestModel` + fake
streaming/tracing, no network) live in the SDK repo at
`tests/lib/core/harness/test_harness_pydantic_ai_sync.py`.
