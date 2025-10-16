# [Sync] Streaming

## What You'll Learn

Stream responses progressively using async generators instead of returning a single message. Enables showing partial results as they're generated.

**Use case:** LLM responses, large data processing, or any operation where you want to show progress.

## Quick Start

```bash
cd examples/tutorials/00_sync/020_streaming
uv run agentex agents run --manifest manifest.yaml
```

## Key Code

```python
@acp.on_message_send
async def handle_message_send(params: SendMessageParams):
    async def stream_response():
        for chunk in response_chunks:
            yield TaskMessageUpdate(content=TextContent(...))

    return stream_response()
```

Return an async generator instead of a single response - each `yield` sends an update to the client.
