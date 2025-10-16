# [Temporal] OpenAI Agents SDK - Hello World

## What You'll Learn

The OpenAI Agents SDK plugin automatically converts LLM calls into durable Temporal activities. When `Runner.run()` executes, the LLM invocation becomes an `invoke_model_activity` visible in Temporal UI with full observability, automatic retries, and durability.

**Key insight:** You don't need to wrap agent calls in activities manually - the plugin handles this automatically, making non-deterministic LLM calls work seamlessly in Temporal workflows.

## Quick Start

```bash
cd examples/tutorials/10_agentic/10_temporal/060_open_ai_agents_sdk_hello_world
uv run agentex agents run --manifest manifest.yaml
```

**Monitor:** Open Temporal UI at http://localhost:8080 to see automatic activity creation.

## Try It

1. Send a message to the agent (it responds in haikus)
2. Open Temporal UI at http://localhost:8080
3. Find your workflow execution
4. Look for the `invoke_model_activity` - this was created automatically
5. Inspect the activity to see:
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
