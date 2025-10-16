# [Sync] Hello ACP

## What You'll Learn

The simplest agent type: synchronous request/response pattern with a single `@acp.on_message_send` handler. Best for stateless operations that complete immediately.

**When to use sync:** Quick responses, no long-running operations, no need for task management or durability.

## Quick Start

```bash
cd examples/tutorials/00_sync/000_hello_acp
uv run agentex agents run --manifest manifest.yaml
```

## Key Code

```python
@acp.on_message_send
async def handle_message_send(params: SendMessageParams):
    return TextContent(
        author="agent",
        content=f"Echo: {params.content.content}"
    )
```

That's it - one handler, immediate response. No task creation, no state management.
