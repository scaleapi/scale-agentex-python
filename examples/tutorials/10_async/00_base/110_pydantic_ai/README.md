# Tutorial 110 (async/base): Pydantic AI Agent

This tutorial demonstrates how to build an **async** Pydantic AI agent on AgentEx with:
- Tool calling (Pydantic AI handles the tool loop internally)
- Streaming token output via Redis (text + reasoning tokens stream as deltas)
- Task lifecycle hooks (create / event-send / cancel)

This is the async counterpart to the sync tutorial at [`00_sync/040_pydantic_ai`](../../../00_sync/040_pydantic_ai/).

## Key Concepts

### Async ACP
Unlike sync ACP (HTTP request/response with chunked streaming back), async ACP uses **Redis** for streaming. The HTTP call returns immediately when an event is acknowledged; the agent then pushes updates to Redis on its own schedule. The UI subscribes to Redis to receive deltas.

### Pydantic AI Integration
- **Agent**: A single `pydantic_ai.Agent` that owns the model and tools. No graph required.
- **`@agent.tool_plain`**: Registers a Python function as a tool. Pydantic AI infers the schema from type hints and docstring.
- **`agent.run_stream_events(...)`**: Yields `AgentStreamEvent`s (`PartStartEvent` / `PartDeltaEvent` / `PartEndEvent` / `FunctionToolResultEvent`) as the model produces them.

### Streaming
The helper `stream_pydantic_ai_events(stream, task_id)` consumes the Pydantic AI event stream and writes Agentex updates to Redis via `adk.streaming.streaming_task_message_context(...)`:
- **Text and thinking tokens** stream as Redis deltas inside coalesced contexts.
- **Tool requests and tool responses** are emitted as **discrete full messages** (no token-level arg streaming). To stream tool-call argument tokens, use the sync converter — see [`00_sync/040_pydantic_ai`](../../../00_sync/040_pydantic_ai/).

## Files

| File | Description |
|------|-------------|
| `project/acp.py` | Async ACP server with task lifecycle handlers |
| `project/agent.py` | Pydantic AI agent + tool registration |
| `project/tools.py` | Tool definitions (weather example) |
| `tests/test_agent.py` | Integration tests |
| `manifest.yaml` | Agent configuration |

## Running Locally

```bash
# From this directory
agentex agents run
```

## Running Tests

```bash
pytest tests/test_agent.py -v
```

## Sync vs Async — How the Code Differs

This tutorial uses the same `project/agent.py` and `project/tools.py` as the sync version. The only meaningful differences live in `project/acp.py`:

| Concern | Sync (`s040-pydantic-ai`) | Async (`ab110-pydantic-ai`) |
|---|---|---|
| ACP type | `FastACP.create(acp_type="sync")` | `FastACP.create(acp_type="async", config=AsyncACPConfig(type="base"))` |
| Handler hook | `@acp.on_message_send` returns/yields events | `@acp.on_task_event_send` returns nothing |
| Stream output | `yield event` (chunked HTTP) | `await context.stream_update(...)` (Redis) |
| Tool calls | Args stream as `ToolRequestDelta` tokens | Args arrive in one full message |
| Lifecycle | Ephemeral (no task hooks) | `on_task_create` + `on_task_cancel` form a durable task contract |

## Notes

- Multi-turn conversation memory is not wired here. Pydantic AI does not ship a checkpointer; to add memory, load prior messages via `adk.messages.list(task_id=...)` and pass them to `agent.run_stream_events(..., message_history=...)`.
- Reasoning/thinking tokens are not exercised by `gpt-4o-mini`. Swap to a reasoning-capable model if you want to test that branch end-to-end.
