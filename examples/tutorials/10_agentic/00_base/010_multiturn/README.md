# [Agentic] Multiturn

Handle multi-turn conversations in agentic agents with task-based state management. Each task maintains its own conversation history automatically.

## What You'll Learn
- How tasks maintain conversation state across multiple exchanges
- Difference between sync and agentic multiturn patterns
- Building stateful conversational agents with minimal code

## Prerequisites
- Development environment set up (see [main repo README](https://github.com/scaleapi/scale-agentex))
- Backend services running: `make dev` from repository root
- Understanding of basic agentic agents (see [000_hello_acp](../000_hello_acp/))

## Quick Start

```bash
cd examples/tutorials/10_agentic/00_base/010_multiturn
uv run agentex agents run --manifest manifest.yaml
```

## Key Pattern

Unlike sync agents where you manually track conversation history, agentic agents automatically maintain state within each task:

```python
@app.on_task_event_send()
async def on_task_event_send(event_send: TaskEventSendInput):
    # The task's messages list automatically includes all previous exchanges
    messages = event_send.task.messages

    # No need to manually pass history - it's already there!
    response = await openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages
    )

    return {"content": response.choices[0].message.content}
```

## Try It

1. Start the agent with the command above
2. Open the web UI or use the notebook to create a task
3. Send multiple messages in the same task:
   - "What's 25 + 17?"
   - "What was that number again?"
   - "Multiply it by 2"
4. Notice the agent remembers context from previous exchanges

## When to Use
- Conversational agents that need memory across exchanges
- Chat interfaces where users ask follow-up questions
- Agents that build context over time within a session

## Why This Matters
Task-based state management eliminates the complexity of manually tracking conversation history. The AgentEx platform handles state persistence automatically, making it easier to build stateful agents without custom session management code.

**Comparison:** In the sync version ([00_sync/010_multiturn](../../../00_sync/010_multiturn/)), you manually manage conversation history. Here, the task object does it for you.

**Next:** [020_streaming](../020_streaming/) - Add real-time streaming responses
