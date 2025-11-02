"""Temporal streaming hooks for OpenAI Agents SDK lifecycle events.

This module provides a convenience class for streaming agent lifecycle events
to the AgentEx UI via Temporal activities.
"""

import logging
from typing import Any, override
from datetime import timedelta

from agents import Tool, Agent, RunHooks, RunContextWrapper
from temporalio import workflow
from agents.tool_context import ToolContext

from agentex.types.text_content import TextContent
from agentex.types.task_message_content import ToolRequestContent, ToolResponseContent
from agentex.lib.core.temporal.plugins.openai_agents.hooks.activities import stream_lifecycle_content

logger = logging.getLogger(__name__)


class TemporalStreamingHooks(RunHooks):
    """Convenience hooks class for streaming OpenAI Agent lifecycle events to the AgentEx UI.

    This class automatically streams agent lifecycle events (tool calls, handoffs) to the
    AgentEx UI via Temporal activities. It subclasses the OpenAI Agents SDK's RunHooks
    to intercept lifecycle events and forward them for real-time UI updates.

    Lifecycle events streamed:
        - Tool requests (on_tool_start): Streams when a tool is about to be invoked
        - Tool responses (on_tool_end): Streams the tool's execution result
        - Agent handoffs (on_handoff): Streams when control transfers between agents

    Usage:
        Basic usage - streams all lifecycle events::

            from agentex.lib.core.temporal.plugins.openai_agents import TemporalStreamingHooks

            hooks = TemporalStreamingHooks(task_id="abc123")
            result = await Runner.run(agent, input, hooks=hooks)

        Advanced - subclass for custom behavior::

            class MyCustomHooks(TemporalStreamingHooks):
                async def on_tool_start(self, context, agent, tool):
                    # Add custom logic before streaming
                    await self.my_custom_logging(tool)
                    # Call parent to stream to UI
                    await super().on_tool_start(context, agent, tool)

                async def on_agent_start(self, context, agent):
                    # Override empty methods for additional tracking
                    print(f"Agent {agent.name} started")

    Power users can ignore this class and subclass agents.RunHooks directly for full control.

    Note:
        Tool arguments are not available in hooks due to OpenAI SDK architecture.
        The SDK's hook signature doesn't include tool arguments - they're only passed
        to the actual tool function. This is why arguments={} in ToolRequestContent.

    Attributes:
        task_id: The AgentEx task ID for routing streamed events
        timeout: Timeout for streaming activity calls (default: 10 seconds)
    """

    def __init__(
        self,
        task_id: str,
        timeout: timedelta = timedelta(seconds=10),
    ):
        """Initialize the streaming hooks.

        Args:
            task_id: AgentEx task ID for routing streamed events to the correct UI session
            timeout: Timeout for streaming activity invocations (default: 10 seconds)
        """
        super().__init__()
        self.task_id = task_id
        self.timeout = timeout

    @override
    async def on_agent_start(self, context: RunContextWrapper, agent: Agent) -> None:  # noqa: ARG002
        """Called when an agent starts execution.

        Default implementation logs the event. Override to add custom behavior.

        Args:
            context: The run context wrapper
            agent: The agent that is starting
        """
        logger.debug(f"[TemporalStreamingHooks] Agent '{agent.name}' started execution")

    @override
    async def on_agent_end(self, context: RunContextWrapper, agent: Agent, output: Any) -> None:  # noqa: ARG002
        """Called when an agent completes execution.

        Default implementation logs the event. Override to add custom behavior.

        Args:
            context: The run context wrapper
            agent: The agent that completed
            output: The agent's output
        """
        logger.debug(f"[TemporalStreamingHooks] Agent '{agent.name}' completed execution with output type: {type(output).__name__}")

    @override
    async def on_tool_start(self, context: RunContextWrapper, agent: Agent, tool: Tool) -> None:  # noqa: ARG002
        """Stream tool request when a tool starts execution.

        Extracts the tool_call_id from the context and streams a ToolRequestContent
        message to the UI showing that the tool is about to execute.

        Note: Tool arguments are not available in the hook context due to OpenAI SDK
        design. The hook signature doesn't include tool arguments - they're passed
        directly to the tool function instead. We send an empty dict as a placeholder.

        Args:
            context: The run context wrapper (will be a ToolContext with tool_call_id)
            agent: The agent executing the tool
            tool: The tool being executed
        """
        tool_context = context if isinstance(context, ToolContext) else None
        tool_call_id = tool_context.tool_call_id if tool_context else f"call_{id(tool)}"

        await workflow.execute_activity_method(
            stream_lifecycle_content,
            args=[
                self.task_id,
                ToolRequestContent(
                    author="agent",
                    tool_call_id=tool_call_id,
                    name=tool.name,
                    arguments={},  # Not available in hook context - SDK limitation
                ),
            ],
            start_to_close_timeout=self.timeout,
        )

    @override
    async def on_tool_end(
        self, context: RunContextWrapper, agent: Agent, tool: Tool, result: str  # noqa: ARG002
    ) -> None:
        """Stream tool response when a tool completes execution.

        Extracts the tool_call_id and streams a ToolResponseContent message to the UI
        showing the tool's execution result.

        Args:
            context: The run context wrapper (will be a ToolContext with tool_call_id)
            agent: The agent that executed the tool
            tool: The tool that was executed
            result: The tool's execution result
        """
        tool_context = context if isinstance(context, ToolContext) else None
        tool_call_id = (
            getattr(tool_context, "tool_call_id", f"call_{id(tool)}")
            if tool_context
            else f"call_{id(tool)}"
        )

        await workflow.execute_activity_method(
            stream_lifecycle_content,
            args=[
                self.task_id,
                ToolResponseContent(
                    author="agent",
                    tool_call_id=tool_call_id,
                    name=tool.name,
                    content=result,
                ),
            ],
            start_to_close_timeout=self.timeout,
        )

    @override
    async def on_handoff(
        self, context: RunContextWrapper, from_agent: Agent, to_agent: Agent  # noqa: ARG002
    ) -> None:
        """Stream handoff message when control transfers between agents.

        Sends a text message to the UI indicating that one agent is handing off
        to another agent.

        Args:
            context: The run context wrapper
            from_agent: The agent transferring control
            to_agent: The agent receiving control
        """
        await workflow.execute_activity_method(
            stream_lifecycle_content,
            args=[
                self.task_id,
                TextContent(
                    author="agent",
                    content=f"Handoff from {from_agent.name} to {to_agent.name}",
                    type="text",
                ),
            ],
            start_to_close_timeout=self.timeout,
        )
