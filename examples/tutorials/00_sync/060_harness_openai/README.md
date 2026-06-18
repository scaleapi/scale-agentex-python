# Sync OpenAI Agents on the unified harness surface

A sync (HTTP) Agentex agent that runs the OpenAI Agents SDK and delivers its
output through the **unified harness surface**.

## What this demonstrates

The OpenAI Agents SDK produces native streaming events. This tutorial wraps a
`Runner.run_streamed` result in an `OpenAITurn` — the provider -> canonical
`StreamTaskMessage*` adapter — and forwards the canonical stream to the frontend
via `UnifiedEmitter.yield_turn`. The same `OpenAITurn` flows unchanged through
`auto_send_turn` in the async (`130_harness_openai`) and temporal
(`140_harness_openai`) variants; only the delivery method differs.

```python
result = Runner.run_streamed(starting_agent=agent, input=user_message)
turn = OpenAITurn(result=result, model="gpt-4o")
emitter = UnifiedEmitter(task_id=task_id, trace_id=task_id, parent_span_id=parent_span_id)
async for event in emitter.yield_turn(turn):
    yield event
```

## Run it

```bash
agentex agents run --manifest manifest.yaml
```

## Test it

The offline test exercises the harness wiring without a server or API key:

```bash
pytest tests/test_agent.py -v
```
