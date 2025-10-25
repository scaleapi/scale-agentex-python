"""
Utility functions for testing AgentEx agentic agents.

This module provides helper functions for working with agentic (non-temporal) agents,
including task creation, event sending, response polling, and streaming.
"""

import json
import time
import asyncio
from typing import Optional, AsyncGenerator
from datetime import datetime, timezone

from agentex._client import AsyncAgentex
from agentex.types.task_message import TaskMessage
from agentex.types.agent_rpc_params import ParamsSendEventRequest
from agentex.types.agent_rpc_result import StreamTaskMessageDone, StreamTaskMessageFull
from agentex.types.text_content_param import TextContentParam


async def send_event_and_poll_yielding(
    client: AsyncAgentex,
    agent_id: str,
    task_id: str,
    user_message: str,
    timeout: int = 30,
    sleep_interval: float = 1.0,
) -> AsyncGenerator[TaskMessage, None]:
    """
    Send an event to an agent and poll for responses, yielding messages as they arrive.

    Polls continuously until timeout is hit or the caller exits the loop.

    Args:
        client: AgentEx client instance
        agent_id: The agent ID
        task_id: The task ID
        user_message: The message content to send
        timeout: Maximum seconds to wait for a response (default: 30)
        sleep_interval: Seconds to sleep between polls (default: 1.0)

    Yields:
        TaskMessage objects as they are discovered during polling
    """
    # Send the event
    event_content = TextContentParam(type="text", author="user", content=user_message)

    # Capture timestamp before sending to account for clock skew
    # Subtract 1 second buffer to ensure we don't filter out messages we just created
    messages_created_after = time.time() - 1.0

    await client.agents.send_event(
        agent_id=agent_id, params=ParamsSendEventRequest(task_id=task_id, content=event_content)
    )
    # Poll continuously until timeout
    # Poll for messages created after we sent the event
    async for message in poll_messages(
        client=client,
        task_id=task_id,
        timeout=timeout,
        sleep_interval=sleep_interval,
        messages_created_after=messages_created_after,
    ):
        yield message


async def poll_messages(
    client: AsyncAgentex,
    task_id: str,
    timeout: int = 30,
    sleep_interval: float = 1.0,
    messages_created_after: Optional[float] = None,
) -> AsyncGenerator[TaskMessage, None]:
    # Keep track of messages we've already yielded
    seen_message_ids = set()
    start_time = datetime.now()

    # Poll continuously until timeout
    while (datetime.now() - start_time).seconds < timeout:
        messages = await client.messages.list(task_id=task_id)
        # print("DEBGUG: Messages found: ", messages)
        new_messages_found = 0
        for message in messages:
            # Skip if we've already yielded this message
            if message.id in seen_message_ids:
                continue

            # Check if message passes timestamp filter
            if messages_created_after and message.created_at:
                # If message.created_at is timezone-naive, assume it's UTC
                if message.created_at.tzinfo is None:
                    msg_timestamp = message.created_at.replace(tzinfo=timezone.utc).timestamp()
                else:
                    msg_timestamp = message.created_at.timestamp()
                if msg_timestamp < messages_created_after:
                    continue

            # Yield new messages that pass the filter
            seen_message_ids.add(message.id)
            new_messages_found += 1

            # This yield should transfer control back to the caller
            yield message

            # If we see this print, it means the caller consumed the message and we resumed
        # Sleep before next poll
        await asyncio.sleep(sleep_interval)


async def send_event_and_stream(
    client: AsyncAgentex,
    agent_id: str,
    task_id: str,
    user_message: str,
    timeout: int = 30,
):
    """
    Send an event to an agent and stream the response, yielding events as they arrive.

    This function now uses stream_agent_response() under the hood and yields events
    up the stack as they arrive.

    Args:
        client: AgentEx client instance
        agent_id: The agent ID
        task_id: The task ID
        user_message: The message content to send
        timeout: Maximum seconds to wait for stream completion (default: 30)

    Yields:
        Parsed event dictionaries as they arrive from the stream

    Raises:
        Exception: If streaming fails
    """
    # Send the event
    event_content = TextContentParam(type="text", author="user", content=user_message)

    await client.agents.send_event(agent_id=agent_id, params={"task_id": task_id, "content": event_content})

    # Stream the response using stream_agent_response and yield events up the stack
    async for event in stream_agent_response(
        client=client,
        task_id=task_id,
        timeout=timeout,
    ):
        yield event


async def stream_agent_response(
    client: AsyncAgentex,
    task_id: str,
    timeout: int = 30,
):
    """
    Stream the agent response for a given task, yielding events as they arrive.

    Args:
        client: AgentEx client instance
        task_id: The task ID to stream messages from
        timeout: Maximum seconds to wait for stream completion (default: 30)

    Yields:
        Parsed event dictionaries as they arrive from the stream
    """
    try:
        # Add explicit timeout wrapper to force exit after timeout seconds
        async with asyncio.timeout(timeout):
            async with client.tasks.with_streaming_response.stream_events(task_id=task_id, timeout=timeout) as stream:
                async for line in stream.iter_lines():
                    if line.startswith("data: "):
                        # Parse the SSE data
                        data = line.strip()[6:]  # Remove "data: " prefix
                        event = json.loads(data)
                        # Yield each event immediately as it arrives
                        yield event

    except asyncio.TimeoutError:
        print(f"[DEBUG] Stream timed out after {timeout}s")
    except Exception as e:
        print(f"[DEBUG] Stream error: {e}")

async def stream_task_messages(
    client: AsyncAgentex,
    task_id: str,
    timeout: int = 30,
) -> AsyncGenerator[TaskMessage, None]:
    """
    Stream the task messages for a given task, yielding messages as they arrive.
    """
    async for event in stream_agent_response(
        client=client,
        task_id=task_id,
        timeout=timeout,
    ):
        msg_type = event.get("type")
        task_message: Optional[TaskMessage] = None
        if msg_type == "full":
            task_message_update_full = StreamTaskMessageFull.model_validate(event)
            if task_message_update_full.parent_task_message and task_message_update_full.parent_task_message.id:
                finished_message = await client.messages.retrieve(task_message_update_full.parent_task_message.id)
                task_message = finished_message
        elif msg_type == "done":
            task_message_update_done = StreamTaskMessageDone.model_validate(event)
            if task_message_update_done.parent_task_message and task_message_update_done.parent_task_message.id:
                finished_message = await client.messages.retrieve(task_message_update_done.parent_task_message.id)
                task_message = finished_message
        if task_message:
            yield task_message



def validate_text_in_response(expected_text: str, message: TaskMessage) -> bool:
    """
    Validate that expected text appears in any of the messages.

    Args:
        expected_text: The text to search for (case-insensitive)
        messages: List of message objects to search

    Returns:
        True if text is found, False otherwise
    """
    for message in messages:
        if message.content and message.content.type == "text":
            if expected_text.lower() in message.content.content.lower():
                return True
    return False
