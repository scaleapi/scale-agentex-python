# [Agentic] Hello ACP

Agentic agents use three handlers for async task management: `on_task_create`, `on_task_event_send`, and `on_task_cancel`. Unlike sync agents, tasks persist and can receive multiple events over time.

## What You'll Learn
- The three-handler pattern for agentic agents
- How tasks differ from sync messages
- When to use agentic vs sync agents

## Prerequisites
- Development environment set up (see [main repo README](https://github.com/scaleapi/scale-agentex))
- Backend services running: `make dev` from repository root
- Understanding of sync agents (see [00_sync/000_hello_acp](../../../00_sync/000_hello_acp/))

## Quick Start

```bash
cd examples/tutorials/10_agentic/00_base/000_hello_acp
uv run agentex agents run --manifest manifest.yaml
```

## Key Pattern

```python
@acp.on_task_create
async def handle_task_create(params: CreateTaskParams):
    # Initialize task state, send welcome message

@acp.on_task_event_send
async def handle_event_send(params: SendEventParams):
    # Handle each message/event in the task

@acp.on_task_cancel
async def handle_task_cancel(params: CancelTaskParams):
    # Cleanup when task is cancelled
```

Three handlers instead of one, giving you full control over task lifecycle. Tasks can receive multiple events and maintain state across them.

## When to Use
- Conversational agents that need memory
- Operations that require task tracking
- Agents that need lifecycle management (initialization, cleanup)
- Building towards production systems

## Why This Matters
The task-based model is the foundation of production agents. Unlike sync agents where each message is independent, agentic agents maintain persistent tasks that can receive multiple events, store state, and have full lifecycle management. This is the stepping stone to Temporal-based agents.

**Next:** [010_multiturn](../010_multiturn/) - Add conversation memory
