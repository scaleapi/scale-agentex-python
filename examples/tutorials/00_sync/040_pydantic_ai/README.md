# Tutorial 040: Sync Pydantic AI Agent

This tutorial demonstrates how to build a **synchronous** Pydantic AI agent on AgentEx with:
- Tool calling (Pydantic AI handles the tool loop internally)
- Streaming token output (including token-by-token tool-call argument streaming)

## Key Concepts

### Sync ACP
The sync ACP model uses HTTP request/response for communication. The `@acp.on_message_send` handler receives a message and yields streaming events back to the client.

### Pydantic AI Integration
- **Agent**: A single `pydantic_ai.Agent` that owns the model and tools. No graph required — Pydantic AI runs its own tool-call loop until the model is done.
- **`@agent.tool_plain`**: Registers a Python function as a tool. Pydantic AI infers the schema from type hints and docstring.
- **`agent.run_stream_events(...)`**: Yields `AgentStreamEvent`s (PartStartEvent / PartDeltaEvent / PartEndEvent / FunctionToolResultEvent) as the model produces them.

### Streaming
The agent streams tokens and tool-call arguments as they're generated using `convert_pydantic_ai_to_agentex_events()`, which adapts Pydantic AI's stream into AgentEx `TaskMessageUpdate` events. Notably, **tool-call arguments stream as `ToolRequestDelta` tokens** rather than arriving as a single complete payload — a richer experience than what OpenAI Agents SDK currently exposes.

## Files

| File | Description |
|------|-------------|
| `project/acp.py` | ACP server and message handler |
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

## Notes

- Multi-turn conversation memory is not wired in this tutorial. Pydantic AI does not ship a checkpointer like LangGraph; to add memory, load prior messages via `adk.messages.list(task_id=...)` and pass them to `agent.run_stream_events(..., message_history=...)`.
- Reasoning/thinking tokens are not exercised here because `gpt-4o-mini` does not emit `ThinkingPart`s. Swap to a reasoning-capable model (e.g. `openai:o1-mini` via Pydantic AI's appropriate provider) if you want to test that branch end-to-end.
