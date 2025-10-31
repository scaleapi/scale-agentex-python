# [Sync] Hello ACP

This is a simple AgentEx agent that just says hello and acknowledges the user's message to show which ACP methods need to be implemented for the sync ACP type.
The simplest agent type: synchronous request/response pattern with a single `@acp.on_message_send` handler. Best for stateless operations that complete immediately.

## What You'll Learn
- Building a basic synchronous agent
- The `@acp.on_message_send` handler pattern
- When to use sync vs agentic agents

## Prerequisites
- Development environment set up (see [main repo README](https://github.com/scaleapi/scale-agentex))
- Backend services running: `make dev` from repository (agentex) root

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

## When to Use
- Simple chatbots with no memory requirements
- Quick Q&A or information lookup agents
- Prototyping and testing agent responses
- Operations that complete in under a second

## Why This Matters
Sync agents are the simplest way to get started with AgentEx. They're perfect for learning the basics and building stateless agents. Once you need conversation memory or task tracking, you'll graduate to agentic agents.

**Next:** [010_multiturn](../010_multiturn/) - Add conversation memory to your agent
