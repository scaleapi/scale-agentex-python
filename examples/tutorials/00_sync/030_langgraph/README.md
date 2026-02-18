# Tutorial 030: Sync LangGraph Agent

This tutorial demonstrates how to build a **synchronous** LangGraph agent on AgentEx with:
- Tool calling (ReAct pattern)
- Streaming token output
- Multi-turn conversation memory via AgentEx checkpointer
- Tracing integration

## Graph Structure

![Graph](graph.png)

## Key Concepts

### Sync ACP
The sync ACP model uses HTTP request/response for communication. The `@acp.on_message_send` handler receives a message and yields streaming events back to the client.

### LangGraph Integration
- **StateGraph**: Defines the agent's state machine with `AgentState` (message history)
- **ToolNode**: Automatically executes tool calls from the LLM
- **tools_condition**: Routes between tool execution and final response
- **Checkpointer**: Uses AgentEx's HTTP checkpointer for cross-request memory

### Streaming
The agent streams tokens as they're generated using `convert_langgraph_to_agentex_events()`, which converts LangGraph's stream events into AgentEx `TaskMessageUpdate` events.

## Files

| File | Description |
|------|-------------|
| `project/acp.py` | ACP server and message handler |
| `project/graph.py` | LangGraph state graph definition |
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
