# [Temporal] Agent Chat

## What You'll Learn

Combine streaming responses, multi-turn chat, tool calling, and tracing - all with Temporal's durability guarantees. This shows how to build a complete conversational agent that can survive failures.

**Use case:** Production chatbots with tools, long-running customer service conversations, or any agent that needs both capabilities and reliability.

## Quick Start

```bash
cd examples/tutorials/10_agentic/10_temporal/010_agent_chat
uv run agentex agents run --manifest manifest.yaml
```

## Key Pattern

- **Streaming**: Progressive response generation with `adk.messages.create()`
- **Multi-turn**: Conversation history maintained in durable workflow state
- **Tools**: Agent can call functions to perform actions
- **Tracing**: Full observability of tool calls and LLM interactions
- **Durability**: All of the above survives worker restarts

**Monitor:** Open Temporal UI at http://localhost:8080 to see the workflow and all tool call activities.

## Key Insight

In base agentic agents, all this state lives in memory and is lost on crash. With Temporal, the entire conversation - history, tool calls, intermediate state - is durably persisted. The agent can pick up a conversation that paused days ago as if no time passed.
