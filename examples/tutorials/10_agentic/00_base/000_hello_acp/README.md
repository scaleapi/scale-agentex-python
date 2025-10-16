# [Agentic] Hello ACP

## What You'll Learn

Agentic agents use three handlers for async task management: `on_task_create`, `on_task_event_send`, and `on_task_cancel`. Unlike sync agents, tasks persist and can receive multiple events over time.

**When to use agentic:** Long-running conversations, stateful operations, or when you need task lifecycle management.

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
