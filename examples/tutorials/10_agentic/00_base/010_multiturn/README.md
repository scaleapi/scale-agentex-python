# [Agentic] Multiturn

## What You'll Learn

Handle multi-turn conversations in agentic agents with task-based state management. Each task maintains its own conversation history.

**Use case:** Conversational agents that need to remember context across multiple exchanges within a task.

## Quick Start

```bash
cd examples/tutorials/10_agentic/00_base/010_multiturn
uv run agentex agents run --manifest manifest.yaml
```

## Key Pattern

In sync agents, you manually pass conversation history. In agentic agents, the task itself maintains state across multiple `on_task_event_send` calls, making it easier to build stateful conversations.
