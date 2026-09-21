# Tutorial: Sync LangGraph Agent

This tutorial demonstrates how to build a **synchronous** LangGraph agent on AgentEx
using the **unified harness surface**:

```python
turn = LangGraphTurn(stream, model=None)
emitter = UnifiedEmitter(task_id=task_id, trace_id=task_id, ...)
async for event in emitter.yield_turn(turn):
    yield event
```

The `LangGraphTurn` + `UnifiedEmitter` path replaces calling the lower-level
``convert_langgraph_to_agentex_events`` helper directly.

## Key Concepts

### Unified Harness

`LangGraphTurn` implements the `HarnessTurn` protocol: it wraps the raw
LangGraph `astream()` generator and exposes `events` (an async generator of
`TaskMessageUpdate`) and `usage()` (token counts captured from the final
`AIMessage`).

`UnifiedEmitter.yield_turn(turn)` iterates the turn's events and yields them
to the sync ACP handler unchanged. The same `LangGraphTurn` object can also be
passed to `UnifiedEmitter.auto_send_turn` in the async/temporal channels.

### AGX1-377 Note

LangGraph emits tool requests as `StreamTaskMessageFull` events (from "updates"
node outputs). The `SpanDeriver` does not open tool spans from Full events
today; that gap is tracked in AGX1-373.

## Files

| File | Description |
|------|-------------|
| `project/acp.py` | ACP server using unified harness (LangGraphTurn + yield_turn) |
| `project/graph.py` | LangGraph state graph (weather example) |
| `project/tools.py` | Tool definitions (weather example) |
| `tests/test_agent.py` | Integration tests |
| `manifest.yaml` | Agent configuration (name: s030-langgraph) |

## Running Locally

```bash
agentex agents run
```

## Running Tests

```bash
pytest tests/test_agent.py -v
```
