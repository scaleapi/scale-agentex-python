# [Temporal] Using Alternative Models with LiteLLM (Gemini)

**Part of the [OpenAI SDK + Temporal integration series](../README.md)**

## What You'll Learn

This tutorial demonstrates how to use Google's Gemini models (or any other LLM provider) with the OpenAI Agents SDK through LiteLLM. The key insight is that LiteLLM provides a unified interface, allowing you to swap models without changing your agent code structure.

**Key insight:** You can use the same OpenAI Agents SDK patterns with any LLM provider supported by LiteLLM - Gemini, Anthropic Claude, Mistral, and many more.

## Prerequisites
- Development environment set up (see [main repo README](https://github.com/scaleapi/scale-agentex))
- Backend services running: `make dev` from repository root (includes Temporal)
- Temporal UI available at http://localhost:8233
- **Google Gemini API key** (see setup below)
- Understanding of OpenAI Agents SDK basics (see [060_open_ai_agents_sdk_hello_world](../060_open_ai_agents_sdk_hello_world/))

## Setup

### 1. Get a Gemini API Key

1. Go to [Google AI Studio](https://aistudio.google.com/apikey)
2. Create a new API key
3. Copy the key for the next step

### 2. Configure the API Key

Add to your environment or `manifest.yaml`:

**Option A: Environment variable**
```bash
export GEMINI_API_KEY="your-gemini-api-key-here"
```

**Option B: In manifest.yaml**
```yaml
agent:
  env:
    GEMINI_API_KEY: "your-gemini-api-key-here"
```

### 3. Install LiteLLM Dependency

The `pyproject.toml` already includes `litellm>=1.52.0`. When you run the agent, dependencies are installed automatically.

## Quick Start

```bash
cd examples/tutorials/10_async/10_temporal/100_gemini_litellm
uv run agentex agents run --manifest manifest.yaml
```

**Monitor:** Open Temporal UI at http://localhost:8233 to see workflow execution.

## Key Code Changes

The main difference from OpenAI examples is using `LitellmModel`:

```python
from agents.extensions.models.litellm_model import LitellmModel

# Create a LiteLLM model pointing to Gemini
gemini_model = LitellmModel(model="gemini/gemini-2.0-flash")

agent = Agent(
    name="Gemini Assistant",
    instructions="You are a helpful assistant powered by Gemini.",
    model=gemini_model,  # Use the LiteLLM model instead of default
)

# Run works exactly the same way
result = await Runner.run(agent, user_messages)
```

## Supported Models

LiteLLM supports many providers. Just change the model string:

| Provider | Model String Example |
|----------|---------------------|
| Google Gemini | `gemini/gemini-2.0-flash`, `gemini/gemini-1.5-pro` |
| Anthropic | `anthropic/claude-3-sonnet-20240229` |
| Mistral | `mistral/mistral-large-latest` |
| Cohere | `cohere/command-r-plus` |
| AWS Bedrock | `bedrock/anthropic.claude-3-sonnet` |

See [LiteLLM Providers](https://docs.litellm.ai/docs/providers) for the full list.

## Why LiteLLM?

**Model Flexibility:** Switch between providers without code changes - just update the model string.

**Unified Interface:** Same OpenAI Agents SDK patterns work with any provider.

**Cost Optimization:** Easily compare costs across providers by switching models.

**Fallback Support:** LiteLLM supports automatic fallbacks if a provider is unavailable.

## Architecture Notes

The Temporal integration remains identical:
- Workflows are durable and survive restarts
- LLM calls are wrapped as activities automatically
- Full observability in Temporal UI
- Automatic retries on failures

The only change is the model provider - everything else works the same.

## When to Use

- Want to use non-OpenAI models with OpenAI Agents SDK
- Need to compare model performance across providers
- Building multi-model systems with fallbacks
- Cost optimization across different providers
- Regulatory requirements for specific model providers

## Troubleshooting

**"GEMINI_API_KEY environment variable is not set"**
- Ensure you've exported the API key or added it to manifest.yaml

**"Model not found" errors**
- Check the model string format matches LiteLLM's expected format
- See [LiteLLM Providers](https://docs.litellm.ai/docs/providers) for correct model names

**Rate limiting errors**
- Gemini has different rate limits than OpenAI
- Consider adding retry logic or using LiteLLM's built-in retry support

**Previous:** [090_claude_agents_sdk_mvp](../090_claude_agents_sdk_mvp/) - Claude SDK integration
