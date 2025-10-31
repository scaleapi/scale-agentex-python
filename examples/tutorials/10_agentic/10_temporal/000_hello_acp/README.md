# [Temporal] Hello ACP

Temporal workflows make agents durable - they survive restarts and can run indefinitely without consuming resources while idle. Instead of handlers, you define a workflow class with `@workflow.run` and `@workflow.signal` methods.

## What You'll Learn
- Building durable agents with Temporal workflows
- The workflow and signal pattern
- How workflows survive failures and resume automatically
- When to use Temporal vs base agentic agents

## Prerequisites
- Development environment set up (see [main repo README](https://github.com/scaleapi/scale-agentex))
- Backend services running: `make dev` from repository root (includes Temporal)
- Temporal UI available at http://localhost:8233
- Understanding of base agentic agents (see [../../00_base/080_batch_events](../../00_base/080_batch_events/) to understand why Temporal)

## Quick Start

```bash
cd examples/tutorials/10_agentic/10_temporal/000_hello_acp
uv run agentex agents run --manifest manifest.yaml
```

**Monitor:** Check Temporal UI at http://localhost:8233 to see your durable workflow running.

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

## When to Use
- Production agents that need guaranteed execution
- Long-running tasks (hours, days, weeks, or longer)
- Operations that must survive system failures
- Agents with concurrent event handling requirements
- When you need durability and observability

## Why This Matters
**Without Temporal:** If your worker crashes, the agent loses all state and has to start over.

**With Temporal:** The workflow resumes exactly where it left off. If it crashes mid-conversation, Temporal brings it back up with full context intact. Can run for years if needed, only consuming resources when actively processing.

This is the foundation for production-ready agents that handle real-world reliability requirements.

**Next:** [010_agent_chat](../010_agent_chat/) - Build a complete conversational agent with tools
