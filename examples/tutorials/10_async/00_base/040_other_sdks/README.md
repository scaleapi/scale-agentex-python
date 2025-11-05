# [Agentic] Other SDKs

Agents are just Python code - integrate any SDK you want (OpenAI, Anthropic, LangChain, LlamaIndex, custom libraries, etc.). AgentEx doesn't lock you into a specific framework.

## What You'll Learn
- How to integrate OpenAI, Anthropic, or any SDK
- What AgentEx provides vs what you bring
- Framework-agnostic agent development
- Building agents with your preferred tools

## Prerequisites
- Development environment set up (see [main repo README](https://github.com/scaleapi/scale-agentex))
- Backend services running: `make dev` from repository root
- Understanding of agentic agents (see [000_hello_acp](../000_hello_acp/))

## Quick Start

```bash
cd examples/tutorials/10_agentic/00_base/040_other_sdks
uv run agentex agents run --manifest manifest.yaml
```

## Key Insight

AgentEx provides:
- ACP protocol implementation (task management, message handling)
- Deployment infrastructure
- Monitoring and observability

You provide:
- Agent logic using whatever SDK/library you want
- Tools and capabilities specific to your use case

Mix and match OpenAI, Anthropic, LangChain, or roll your own - it's all just Python.

## When to Use
- You have an existing agent codebase to migrate
- Your team prefers specific SDKs or frameworks
- You need features from multiple providers
- You want full control over your agent logic

## Why This Matters
AgentEx is infrastructure, not a framework. We handle deployment, task management, and protocol implementation - you handle the agent logic with whatever tools you prefer. This keeps you flexible and avoids vendor lock-in.

**Next:** [080_batch_events](../080_batch_events/) - See when you need Temporal
