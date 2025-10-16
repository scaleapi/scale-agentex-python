# [Agentic] Other SDKs

## What You'll Learn

Agents are just Python code - integrate any SDK you want (OpenAI, Anthropic, LangChain, LlamaIndex, custom libraries, etc.). AgentEx doesn't lock you into a specific framework.

**Use case:** Using your preferred LLM provider, existing agent frameworks, or custom tooling.

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
