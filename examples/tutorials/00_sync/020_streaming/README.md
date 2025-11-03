# [Sync] Streaming

Stream responses progressively using async generators instead of returning a single message. Enables showing partial results as they're generated.

## What You'll Learn
- How to stream responses using async generators
- The `yield` pattern for progressive updates
- When streaming improves user experience

## Prerequisites
- Development environment set up (see [main repo README](https://github.com/scaleapi/scale-agentex))
- Backend services running: `make dev` from repository root
- Understanding of basic sync agents (see [000_hello_acp](../000_hello_acp/))

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

## When to Use
- Streaming LLM responses (OpenAI, Anthropic, etc.)
- Large data processing with progress updates
- Any operation that takes >1 second to complete
- Improving perceived responsiveness

## Why This Matters
Streaming dramatically improves user experience for longer operations. Instead of waiting 10 seconds for a complete response, users see results immediately as they're generated. This is essential for modern AI agents.

**Next:** Ready for task management? → [10_agentic/00_base/000_hello_acp](../../10_agentic/00_base/000_hello_acp/)
