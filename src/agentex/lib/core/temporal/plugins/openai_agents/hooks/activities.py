"""Temporal activities for streaming agent lifecycle events.

This module provides reusable Temporal activities for streaming content
to the AgentEx UI, designed to work with TemporalStreamingHooks.
"""

from typing import Any, Dict

from temporalio import activity

from agentex.lib import adk
from agentex.types.text_content import TextContent
from agentex.types.task_message_update import StreamTaskMessageFull
from agentex.types.task_message_content import (
    ToolRequestContent,
    ToolResponseContent,
)


def _deserialize_content(data: Dict[str, Any]):
    """Reconstruct the correct content type from a dict using the 'type' discriminator.

    Temporal's payload converter deserializes Union types by trying each variant
    in order, which causes ToolResponseContent to be misdeserialized as TextContent
    (both have 'author' and 'content' fields). This function uses the 'type' field
    to pick the correct Pydantic model.
    """
    content_type = data.get("type")
    if content_type == "tool_request":
        return ToolRequestContent.model_validate(data)
    elif content_type == "tool_response":
        return ToolResponseContent.model_validate(data)
    else:
        return TextContent.model_validate(data)


@activity.defn(name="stream_lifecycle_content")
async def stream_lifecycle_content(
    task_id: str,
    content: Dict[str, Any],
) -> None:
    """Stream agent lifecycle content to the AgentEx UI.

    This is a universal streaming activity that can handle any type of agent
    lifecycle content (text messages, tool requests, tool responses, etc.).
    It uses the AgentEx streaming context to send updates to the UI in real-time.

    Designed to work seamlessly with TemporalStreamingHooks. The hooks class
    will call this activity automatically when lifecycle events occur.

    Note: The content parameter is a dict (not a typed Union) because Temporal's
    payload converter misdeserializes Union types with overlapping fields.
    The correct Pydantic model is reconstructed using the 'type' discriminator.

    Args:
        task_id: The AgentEx task ID for routing the content to the correct UI session
        content: Dict with a 'type' field that determines the content model:
            - type="text": TextContent (plain text messages, handoff notifications)
            - type="tool_request": ToolRequestContent (tool invocation with call_id)
            - type="tool_response": ToolResponseContent (tool result with call_id)

    Note:
        This activity is non-blocking and will not throw exceptions to the workflow.
        Any streaming errors are logged but do not fail the activity. This ensures
        that streaming failures don't break the agent execution.
    """
    try:
        typed_content = _deserialize_content(content)
        async with adk.streaming.streaming_task_message_context(
            task_id=task_id,
            initial_content=typed_content,
        ) as streaming_context:
            await streaming_context.stream_update(
                StreamTaskMessageFull(
                    parent_task_message=streaming_context.task_message,
                    content=typed_content,
                    type="full",
                )
            )
    except Exception as e:
        activity.logger.warning(f"Failed to stream content to task {task_id}: {e}")
