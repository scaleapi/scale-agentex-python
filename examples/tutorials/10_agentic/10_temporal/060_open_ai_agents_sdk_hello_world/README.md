# [Temporal] OpenAI Agents SDK - Hello World

**Part of the [OpenAI SDK + Temporal integration series](../README.md)**

## What You'll Learn

The OpenAI Agents SDK plugin automatically converts LLM calls into durable Temporal activities. When `Runner.run()` executes, the LLM invocation becomes an `invoke_model_activity` visible in Temporal UI with full observability, automatic retries, and durability.

**Key insight:** You don't need to wrap agent calls in activities manually - the plugin handles this automatically, making non-deterministic LLM calls work seamlessly in Temporal workflows.

## Prerequisites
- Development environment set up (see [main repo README](https://github.com/scaleapi/scale-agentex))
- Backend services running: `make dev` from repository root (includes Temporal)
- Temporal UI available at http://localhost:8233
- OpenAI API key configured (see setup below)
- Understanding of Temporal workflows (see [000_hello_acp](../000_hello_acp/))

## Setup

This tutorial uses the OpenAI Agents SDK plugin, which needs to be added in two places:

### 1. Add Plugin to ACP (`project/acp.py`)
```python
from agentex.lib.plugins.openai_agents import OpenAIAgentsPlugin

acp = FastACP.create(
    config=TemporalACPConfig(
        plugins=[OpenAIAgentsPlugin()]  # Add this
    )
)
```

### 2. Add Plugin to Worker (`project/run_worker.py`)
```python
from agentex.lib.plugins.openai_agents import OpenAIAgentsPlugin

worker = AgentexWorker(
    task_queue=task_queue_name,
    plugins=[OpenAIAgentsPlugin()],  # Add this
)
```

### 3. Configure OpenAI API Key
Add to `manifest.yaml`:
```yaml
secrets:
  - name: OPENAI_API_KEY
    value: "your-openai-api-key-here"
```

Or set in `.env` file: `OPENAI_API_KEY=your-key-here`

## Quick Start

```bash
cd examples/tutorials/10_agentic/10_temporal/060_open_ai_agents_sdk_hello_world
uv run agentex agents run --manifest manifest.yaml
```

**Monitor:** Open Temporal UI at http://localhost:8233 to see automatic activity creation.

## Try It

1. Send a message to the agent (it responds in haikus)
2. Check the agent response:

![Agent Response](../_images/hello_world_response.png)

3. Open Temporal UI at http://localhost:8233
4. Find your workflow execution
5. Look for the `invoke_model_activity` - this was created automatically:

![Temporal UI](../_images/hello_world_temporal.png)

6. Inspect the activity to see:
   - Input parameters (your message)
   - Output (agent's haiku response)
   - Execution time
   - Retry attempts (if any failures occurred)

## Key Code

```python
# This simple call automatically becomes a durable Temporal activity:
agent = Agent(name="Haiku Assistant", instructions="...")
result = await Runner.run(agent, user_message)
```

The magic happens behind the scenes - no manual activity wrapping needed. The conversation is now durable and survives process restarts.

## Why This Matters

**Durability:** If your worker crashes mid-conversation, Temporal resumes exactly where it left off. No lost context, no repeated work.

**Observability:** Every LLM call is tracked as an activity with full execution history.

**Reliability:** Failed LLM calls are automatically retried with exponential backoff.

## When to Use
- Building agents with OpenAI's SDK
- Need durability for LLM calls
- Want automatic activity creation without manual wrapping
- Leveraging OpenAI's agent patterns with Temporal's durability

**Next:** [070_open_ai_agents_sdk_tools](../070_open_ai_agents_sdk_tools/) - Add durable tools to your agents
