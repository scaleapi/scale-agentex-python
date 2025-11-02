# [Sync] Multiturn

Handle multi-turn conversations in synchronous agents by manually maintaining conversation history and context between messages.

## What You'll Learn
- How to handle conversation history in sync agents
- Building context from previous messages
- The limitations of stateless multiturn patterns

## Prerequisites
- Development environment set up (see [main repo README](https://github.com/scaleapi/scale-agentex))
- Backend services running: `make dev` from repository root
- Understanding of basic sync agents (see [000_hello_acp](../000_hello_acp/))

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

## When to Use
- Simple chatbots that need conversation memory
- When client can maintain and send conversation history
- Quick prototypes before building full agentic agents

## Why This Matters
While sync agents can handle conversations, you're responsible for managing state on the client side. This becomes complex quickly. For production conversational agents, consider agentic agents ([10_agentic/00_base/010_multiturn](../../10_agentic/00_base/010_multiturn/)) where the platform manages state automatically.

**Next:** [020_streaming](../020_streaming/) - Stream responses in real-time
