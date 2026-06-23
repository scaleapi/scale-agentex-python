# Tutorial: Temporal Harness LangGraph Agent

This tutorial demonstrates how to build a **Temporal-backed** LangGraph agent on
AgentEx, following the ``130_langgraph`` pattern. The agent's LLM node runs as a
durable Temporal activity; the tools node runs inline in the workflow.

This agent is named ``at-harness-langgraph`` to distinguish it from
``at130-langgraph`` (the bespoke reference). The graph and workflow structure are
identical; only the agent name changes.

## Key Concepts

### Temporal + LangGraph

The ``LangGraphPlugin`` from ``temporalio.contrib.langgraph`` turns annotated graph
nodes into Temporal activities or inline workflow callables:

- `agent` node: `execute_in="activity"` (durable, retryable LLM call)
- `tools` node: `execute_in="workflow"` (inline, fast tool execution)

### Message surfacing

After each turn, ``emit_langgraph_messages`` converts the new LangGraph messages
(tool requests, tool responses, final text) into AgentEx ``TaskMessage`` objects
and posts them to the task's message stream.

This is the Temporal-specific path. The non-Temporal async/sync channels use
``UnifiedEmitter.auto_send_turn`` / ``UnifiedEmitter.yield_turn`` with
``LangGraphTurn`` instead.

## Files

| File | Description |
|------|-------------|
| `project/acp.py` | ACP server (Temporal config, LangGraphPlugin) |
| `project/graph.py` | LangGraph graph (agent + tools nodes) |
| `project/workflow.py` | Temporal workflow (signal handlers, emit_langgraph_messages) |
| `project/run_worker.py` | Temporal worker runner |
| `project/tools.py` | Tool definitions (weather example) |
| `tests/test_agent.py` | Integration tests |
| `manifest.yaml` | Agent configuration (name: at-harness-langgraph) |

## Running Locally

```bash
agentex agents run
```

## Running Tests

```bash
pytest tests/test_agent.py -v
```
