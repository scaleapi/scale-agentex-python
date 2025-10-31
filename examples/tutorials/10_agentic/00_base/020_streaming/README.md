# [Agentic] Streaming

Stream responses in agentic agents using `adk.messages.create()` to send progressive updates. More flexible than sync streaming since you can send multiple messages at any time.

## What You'll Learn
- How to stream with explicit message creation
- Difference between sync and agentic streaming patterns
- When to send multiple messages vs single streamed response

## Prerequisites
- Development environment set up (see [main repo README](https://github.com/scaleapi/scale-agentex))
- Backend services running: `make dev` from repository root
- Understanding of agentic basics (see [000_hello_acp](../000_hello_acp/))

## Quick Start

```bash
cd examples/tutorials/10_agentic/00_base/020_streaming
uv run agentex agents run --manifest manifest.yaml
```

## Key Pattern

```python
@acp.on_task_event_send
async def handle_event_send(params: SendEventParams):
    # Send first message
    await adk.messages.create(task_id=task_id, content=...)

    # Do work...

    # Send second message
    await adk.messages.create(task_id=task_id, content=...)
```

Unlike sync streaming (which uses async generators), agentic streaming uses explicit message creation calls, giving you more control over when and what to send.

## When to Use
- Multi-step processes with intermediate results
- Long-running operations with progress updates
- Agents that need to send messages at arbitrary times
- More complex streaming patterns than simple LLM responses

## Why This Matters
Agentic streaming is more powerful than sync streaming. You can send messages at any time, from anywhere in your code, and even from background tasks. This flexibility is essential for complex agents with multiple concurrent operations.

**Next:** [030_tracing](../030_tracing/) - Add observability to your agents
