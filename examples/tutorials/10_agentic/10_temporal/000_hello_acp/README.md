# [Temporal] Hello ACP

## What You'll Learn

Temporal workflows make agents durable - they survive restarts and can run indefinitely without consuming resources while idle. Instead of handlers, you define a workflow class with `@workflow.run` and `@workflow.signal` methods.

**When to use Temporal:** Production agents that need guaranteed execution, long-running tasks (hours/days/weeks), or operations that must survive system failures.

**Coming from base agentic?** See tutorial `080_batch_events` to understand when you need Temporal.

## Quick Start

```bash
cd examples/tutorials/10_agentic/10_temporal/000_hello_acp
uv run agentex agents run --manifest manifest.yaml
```

**Monitor:** Check Temporal UI at http://localhost:8080 to see your durable workflow running.

## Key Pattern

```python
@workflow.defn(name="my-workflow")
class MyWorkflow(BaseWorkflow):
    @workflow.run
    async def on_task_create(self, params: CreateTaskParams):
        # Wait indefinitely for events - workflow stays alive
        await workflow.wait_condition(lambda: self._complete)

    @workflow.signal(name=SignalName.RECEIVE_EVENT)
    async def on_task_event_send(self, params: SendEventParams):
        # Handle events as signals to the workflow
```

## Why This Matters

**Without Temporal:** If your worker crashes, the agent loses all state and has to start over.

**With Temporal:** The workflow resumes exactly where it left off. If it crashes mid-conversation, Temporal brings it back up with full context intact. Can run for years if needed, only consuming resources when actively processing.

This is the foundation for production-ready agents that handle real-world reliability requirements.
