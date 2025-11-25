"""Temporal activities for Claude Agents SDK integration."""

from __future__ import annotations

import os
from typing import Any

from temporalio import activity
from claude_agent_sdk import AgentDefinition, ClaudeSDKClient, ClaudeAgentOptions

from agentex.lib.utils.logging import make_logger
from agentex.lib.core.temporal.plugins.claude_agents.hooks import create_streaming_hooks
from agentex.lib.core.temporal.plugins.claude_agents.message_handler import ClaudeMessageHandler
from agentex.lib.core.temporal.plugins.openai_agents.interceptors.context_interceptor import (
    streaming_task_id,
    streaming_trace_id,
    streaming_parent_span_id,
)

logger = make_logger(__name__)


@activity.defn
async def create_workspace_directory(task_id: str, workspace_root: str | None = None) -> str:
    """Create workspace directory for task - runs as Temporal activity

    Args:
        task_id: Task ID for workspace directory name
        workspace_root: Root directory for workspaces (defaults to .claude-workspace/ in cwd)

    Returns:
        Absolute path to created workspace
    """
    if workspace_root is None:
        # Default to .claude-workspace in current directory
        # Follows Claude SDK's .claude/ convention
        workspace_root = os.path.join(os.getcwd(), ".claude-workspace")

    workspace_path = os.path.join(workspace_root, task_id)
    os.makedirs(workspace_path, exist_ok=True)
    logger.info(f"Created workspace: {workspace_path}")
    return workspace_path


@activity.defn(name="run_claude_agent_activity")
async def run_claude_agent_activity(
    prompt: str,
    workspace_path: str,
    allowed_tools: list[str],
    permission_mode: str = "acceptEdits",
    system_prompt: str | None = None,
    resume_session_id: str | None = None,
    agents: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute Claude SDK - wrapped in Temporal activity

    This activity:
    1. Gets task_id from ContextVar (set by ContextInterceptor)
    2. Configures Claude with workspace isolation and session resume
    3. Runs Claude SDK and processes messages via ClaudeMessageHandler
    4. Streams messages to UI in real-time
    5. Returns session_id, usage, and cost for next turn

    Args:
        prompt: User message to send to Claude
        workspace_path: Directory for file operations (cwd)
        allowed_tools: List of tools Claude can use (include "Task" for subagents)
        permission_mode: Permission mode (default: acceptEdits)
        system_prompt: Optional system prompt override
        resume_session_id: Optional session ID to resume conversation context
        agents: Optional dict of subagent definitions for Task tool

    Returns:
        dict with "messages", "session_id", "usage", and "cost_usd" keys
    """

    # Get streaming context from ContextVars (set by interceptor)
    task_id = streaming_task_id.get()
    trace_id = streaming_trace_id.get()
    parent_span_id = streaming_parent_span_id.get()

    logger.info(
        f"[run_claude_agent_activity] Starting - "
        f"task_id={task_id}, workspace={workspace_path}, tools={allowed_tools}, "
        f"resume={'YES' if resume_session_id else 'NO (new session)'}, "
        f"subagents={list(agents.keys()) if agents else 'NONE'}"
    )

    # Reconstruct AgentDefinition objects from serialized dicts
    # Temporal serializes dataclasses to dicts, need to recreate them
    agent_defs = None
    if agents:
        agent_defs = {}
        for name, agent_data in agents.items():
            if isinstance(agent_data, AgentDefinition):
                agent_defs[name] = agent_data
            else:
                # Reconstruct from dict
                agent_defs[name] = AgentDefinition(
                    description=agent_data.get('description', ''),
                    prompt=agent_data.get('prompt', ''),
                    tools=agent_data.get('tools'),
                    model=agent_data.get('model'),
                )

    # Create hooks for streaming tool calls and subagent execution
    hooks = create_streaming_hooks(
        task_id=task_id,
        trace_id=trace_id,
        parent_span_id=parent_span_id,
    )

    # Configure Claude with workspace isolation, session resume, subagents, and hooks
    options = ClaudeAgentOptions(
        cwd=workspace_path,
        allowed_tools=allowed_tools,
        permission_mode=permission_mode,  # type: ignore
        system_prompt=system_prompt,
        resume=resume_session_id,
        agents=agent_defs,
        hooks=hooks,  # Tool lifecycle hooks for streaming!
    )

    # Create message handler for streaming
    handler = ClaudeMessageHandler(
        task_id=task_id,
        trace_id=trace_id,
        parent_span_id=parent_span_id,
    )

    # Run Claude and process messages
    try:
        await handler.initialize()

        async with ClaudeSDKClient(options=options) as client:
            await client.query(prompt)

            # Use receive_response() instead of receive_messages()
            # receive_response() yields messages until ResultMessage, then stops
            # receive_messages() is infinite and never completes!
            async for message in client.receive_response():
                await handler.handle_message(message)

        logger.debug(f"Message loop completed, cleaning up...")
        await handler.cleanup()

        results = handler.get_results()
        logger.debug(f"Returning results with keys: {results.keys()}")
        return results

    except Exception as e:
        logger.error(f"[run_claude_agent_activity] Error: {e}", exc_info=True)
        await handler.cleanup()
        raise
