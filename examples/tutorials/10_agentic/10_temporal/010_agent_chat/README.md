# [Temporal] Agent Chat

Combine streaming responses, multi-turn chat, tool calling, and tracing - all with Temporal's durability guarantees. This shows how to build a complete conversational agent that can survive failures.

## What You'll Learn
- Building a complete conversational agent with Temporal
- Combining streaming, multiturn, tools, and tracing
- How all agent capabilities work together with durability
- Production-ready conversational patterns

## Prerequisites
- Development environment set up (see [main repo README](https://github.com/scaleapi/scale-agentex))
- Backend services running: `make dev` from repository root
- Temporal UI available at http://localhost:8233
- Understanding of Temporal basics (see [000_hello_acp](../000_hello_acp/))

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

**Monitor:** Open Temporal UI at http://localhost:8233 to see the workflow and all tool call activities.

## Key Insight

In base agentic agents, all this state lives in memory and is lost on crash. With Temporal, the entire conversation - history, tool calls, intermediate state - is durably persisted. The agent can pick up a conversation that paused days ago as if no time passed.

## When to Use
- Production chatbots with tool capabilities
- Long-running customer service conversations
- Agents that need both reliability and rich features
- Any conversational agent handling real user traffic

## Why This Matters
This is the pattern for real production agents. By combining all capabilities (streaming, tools, tracing) with Temporal's durability, you get an agent that's both feature-rich and reliable. This is what enterprise conversational AI looks like.

**Next:** [020_state_machine](../020_state_machine/) - Add complex multi-phase workflows
