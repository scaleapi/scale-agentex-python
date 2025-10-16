# [Agentic] Streaming

## What You'll Learn

Stream responses in agentic agents using `adk.messages.create()` to send progressive updates. More flexible than sync streaming since you can send multiple messages at any time.

**Use case:** Long-running operations where you want to show progress, or multi-step processes with intermediate results.

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
