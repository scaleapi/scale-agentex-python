# Temporal OpenAI Agents on the unified harness surface

A Temporal-backed Agentex agent that runs the OpenAI Agents SDK and delivers its
output through the **unified harness surface**.

## What this demonstrates

LLM calls are non-deterministic, so they can't run directly in a Temporal
workflow. This tutorial keeps the workflow (`project/workflow.py`)
deterministic and delegates each turn to a custom activity
(`project/activities.py`). The activity uses the SAME `OpenAITurn` adapter as
the sync (`060_harness_openai`) and async (`130_harness_openai`) variants, and
delivers via `UnifiedEmitter.auto_send_turn` — which is designed to run inside
an activity (it writes streaming side effects to Redis and returns the final
text + usage).

```python
# inside the activity:
result = Runner.run_streamed(starting_agent=agent, input=user_message)
turn = OpenAITurn(result=result, model="gpt-4o")
emitter = UnifiedEmitter(task_id=task_id, trace_id=trace_id, parent_span_id=parent_span_id)
turn_result = await emitter.auto_send_turn(turn)
return turn_result.final_text
```

## Run it

```bash
agentex agents run --manifest manifest.yaml
```

This starts both the ACP HTTP server and the Temporal worker.

## Test it

The offline test exercises the activity's delivery path with an injected fake
streaming backend (no server, Temporal, Redis, or API key required):

```bash
pytest tests/test_agent.py -v
```
