# Async OpenAI Agents on the unified harness surface

An async (Redis-streaming) Agentex agent that runs the OpenAI Agents SDK and
delivers its output through the **unified harness surface**.

## What this demonstrates

Same `OpenAITurn` adapter as the sync tutorial (`060_harness_openai`), but the
async ACP pushes the turn to the task stream via
`UnifiedEmitter.auto_send_turn` instead of yielding over HTTP. `auto_send_turn`
returns a `TurnResult` with the accumulated final text and normalized usage.

```python
result = Runner.run_streamed(starting_agent=agent, input=user_message)
turn = OpenAITurn(result=result, model="gpt-4o")
emitter = UnifiedEmitter(task_id=task_id, trace_id=task_id, parent_span_id=parent_span_id)
turn_result = await emitter.auto_send_turn(turn)
```

## Run it

```bash
agentex agents run --manifest manifest.yaml
```

## Test it

The offline test exercises the auto-send delivery path with an injected fake
streaming backend (no server, Redis, or API key required):

```bash
pytest tests/test_agent.py -v
```
