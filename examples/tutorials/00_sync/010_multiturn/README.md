# [Sync] Multiturn

## What You'll Learn

Handle multi-turn conversations in synchronous agents by maintaining conversation history and context between messages.

**Use case:** Chatbots that need to reference previous messages within the same session.

## Quick Start

```bash
cd examples/tutorials/00_sync/010_multiturn
uv run agentex agents run --manifest manifest.yaml
```

## Key Pattern

Sync agents are stateless by default. To handle multi-turn conversations, you need to:
1. Accept conversation history in the request
2. Maintain context across messages
3. Return responses that build on previous exchanges

```python
@acp.on_message_send
async def handle_message_send(params: SendMessageParams):
    # Accept conversation history from client
    history = params.conversation_history

    # Build context from history
    context = build_context(history)

    # Generate response considering full context
    response = generate_response(params.content, context)

    return TextContent(author="agent", content=response)
```

The handler accepts history, builds context, and returns responses that reference previous exchanges.
