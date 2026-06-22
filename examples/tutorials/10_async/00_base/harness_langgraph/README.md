# Tutorial: Async Harness LangGraph Agent

This tutorial demonstrates how to build an **async** LangGraph agent on AgentEx
using the **unified harness surface**:

```python
turn = LangGraphTurn(stream, model=None)
emitter = UnifiedEmitter(task_id=task_id, trace_id=task_id, ...)
result = await emitter.auto_send_turn(turn)
```

Compare with ``100_langgraph``, which uses the bespoke
``stream_langgraph_events`` helper directly.

## Key Concepts

### Unified Harness

`LangGraphTurn` implements the `HarnessTurn` protocol: it wraps the raw
LangGraph `astream()` generator and exposes `events` (an async generator of
`TaskMessageUpdate`) and `usage()` (token counts captured from the final
`AIMessage`).

`UnifiedEmitter.auto_send_turn(turn)` pushes each event to Redis via
`streaming_task_message_context`, accumulates the final text, and returns a
`TurnResult(final_text=..., usage=...)`.

The same `LangGraphTurn` object can also be passed to
`UnifiedEmitter.yield_turn` in the sync channel.

### AGX1-377 Note

LangGraph emits tool requests as `StreamTaskMessageFull` events (from "updates"
node outputs). The `SpanDeriver` does not open tool spans from Full events
today; that gap is tracked in AGX1-373.

## Files

| File | Description |
|------|-------------|
| `project/acp.py` | ACP server using unified harness (LangGraphTurn + auto_send_turn) |
| `project/graph.py` | LangGraph state graph (identical to 100_langgraph) |
| `project/tools.py` | Tool definitions (weather example) |
| `tests/test_agent.py` | Integration tests |
| `manifest.yaml` | Agent configuration (name: a-harness-langgraph) |

## Running Locally

```bash
agentex agents run
```

## Running Tests

```bash
pytest tests/test_agent.py -v
```
