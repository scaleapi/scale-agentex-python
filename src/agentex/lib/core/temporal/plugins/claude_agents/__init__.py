"""Claude Agents SDK integration with Temporal.

This plugin provides integration between Claude Agents SDK and AgentEx's
Temporal-based orchestration platform.

Features:
- Temporal activity wrapper for Claude SDK calls
- Real-time streaming to Redis/UI
- Session resume for conversation context
- Tool call visibility (Read, Write, Bash, etc.)
- Subagent support with nested tracing
- Workspace isolation per task

Architecture:
- activities.py: Temporal activity definitions
- message_handler.py: Message parsing and streaming logic
- Reuses OpenAI's ContextInterceptor for context threading

Usage:
    from agentex.lib.core.temporal.plugins.claude_agents import (
        run_claude_agent_activity,
        create_workspace_directory,
        ContextInterceptor,
    )

    # In worker
    worker = AgentexWorker(
        task_queue=queue_name,
        interceptors=[ContextInterceptor()],
    )

    activities = get_all_activities()
    activities.extend([run_claude_agent_activity, create_workspace_directory])

    await worker.run(activities=activities, workflow=YourWorkflow)
"""

from agentex.lib.core.temporal.plugins.claude_agents.hooks import (
    TemporalStreamingHooks,
    create_streaming_hooks,
)
from agentex.lib.core.temporal.plugins.claude_agents.activities import (
    run_claude_agent_activity,
    create_workspace_directory,
)
from agentex.lib.core.temporal.plugins.claude_agents.message_handler import (
    ClaudeMessageHandler,
)

# Reuse OpenAI's context threading - this is the key to streaming!
from agentex.lib.core.temporal.plugins.openai_agents.interceptors.context_interceptor import (
    ContextInterceptor,
    streaming_task_id,
    streaming_trace_id,
    streaming_parent_span_id,
)

__all__ = [
    # Activities
    "run_claude_agent_activity",
    "create_workspace_directory",
    # Message handling
    "ClaudeMessageHandler",
    # Hooks
    "create_streaming_hooks",
    "TemporalStreamingHooks",
    # Context threading (reused from OpenAI)
    "ContextInterceptor",
    "streaming_task_id",
    "streaming_trace_id",
    "streaming_parent_span_id",
]
