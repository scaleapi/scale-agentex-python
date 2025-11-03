"""Temporal activities for streaming agent lifecycle events.

This module provides reusable Temporal activities for streaming content
to the AgentEx UI, designed to work with TemporalStreamingHooks.
"""

from typing import Union

from temporalio import activity

from agentex.lib import adk
from agentex.types.text_content import TextContent
from agentex.types.task_message_update import StreamTaskMessageFull
from agentex.types.task_message_content import (
    TaskMessageContent,
    ToolRequestContent,
    ToolResponseContent,
)


@activity.defn(name="stream_lifecycle_content")
async def stream_lifecycle_content(
    task_id: str,
    content: Union[TextContent, ToolRequestContent, ToolResponseContent, TaskMessageContent],
) -> None:
    """Stream agent lifecycle content to the AgentEx UI.

    This is a universal streaming activity that can handle any type of agent
    lifecycle content (text messages, tool requests, tool responses, etc.).
    It uses the AgentEx streaming context to send updates to the UI in real-time.

    Designed to work seamlessly with TemporalStreamingHooks. The hooks class
    will call this activity automatically when lifecycle events occur.

    Args:
        task_id: The AgentEx task ID for routing the content to the correct UI session
        content: The content to stream - can be any of:
            - TextContent: Plain text messages (e.g., handoff notifications)
            - ToolRequestContent: Tool invocation requests with call_id and name
            - ToolResponseContent: Tool execution results with call_id and output
            - TaskMessageContent: Generic task message content

    Example:
        Register this activity with your Temporal worker::

            from agentex.lib.core.temporal.plugins.openai_agents import (
                TemporalStreamingHooks,
                stream_lifecycle_content,
            )

            # In your workflow
            hooks = TemporalStreamingHooks(
                task_id=params.task.id,
                stream_activity=stream_lifecycle_content
            )
            result = await Runner.run(agent, input, hooks=hooks)

    Note:
        This activity is non-blocking and will not throw exceptions to the workflow.
        Any streaming errors are logged but do not fail the activity. This ensures
        that streaming failures don't break the agent execution.
    """
    try:
        async with adk.streaming.streaming_task_message_context(
            task_id=task_id,
            initial_content=content,
        ) as streaming_context:
            # Send the content as a full message update
            await streaming_context.stream_update(
                StreamTaskMessageFull(
                    parent_task_message=streaming_context.task_message,
                    content=content,
                    type="full",
                )
            )
    except Exception as e:
        # Log error but don't fail the activity - streaming failures shouldn't break execution
        activity.logger.warning(f"Failed to stream content to task {task_id}: {e}")
