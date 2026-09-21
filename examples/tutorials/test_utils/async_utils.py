"""
Utility functions for testing AgentEx async agents.

This module provides helper functions for working with async (non-temporal) agents,
including task creation, event sending, response polling, and streaming.
"""

import json
import time
import asyncio
import contextlib
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
    yield_updates: bool = True,
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
        yield_updates: If True, yield messages again when their content changes (default: True for streaming)

    Yields:
        TaskMessage objects as they are discovered during polling
    """
    # Send the event
    event_content = TextContentParam(type="text", author="user", content=user_message)

    # Capture timestamp before sending to account for clock skew
    # Subtract 2 second buffer to ensure we don't filter out messages we just created
    # (accounts for clock skew between client and server)
    messages_created_after = time.time() - 2.0

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
        yield_updates=yield_updates,
    ):
        yield message


async def poll_messages(
    client: AsyncAgentex,
    task_id: str,
    timeout: int = 30,
    sleep_interval: float = 1.0,
    messages_created_after: Optional[float] = None,
    yield_updates: bool = False,
) -> AsyncGenerator[TaskMessage, None]:
    """
    Poll for messages continuously until timeout.

    Args:
        client: AgentEx client instance
        task_id: The task ID to poll messages for
        timeout: Maximum seconds to poll (default: 30)
        sleep_interval: Seconds to sleep between polls (default: 1.0)
        messages_created_after: Optional timestamp to filter messages (Unix timestamp)
        yield_updates: If True, yield messages again when their content changes (for streaming)
                      If False, only yield each message ID once (default: False)

    Yields:
        TaskMessage objects as they are discovered or updated
    """
    # Keep track of messages we've already yielded
    seen_message_ids = set()
    # Track message content hashes to detect updates (for streaming)
    message_content_hashes: dict[str, int] = {}
    start_time = datetime.now()

    # Poll continuously until timeout
    while (datetime.now() - start_time).seconds < timeout:
        messages = await client.messages.list(task_id=task_id)

        # Sort messages by created_at to ensure chronological order
        # Use datetime.min for messages without created_at timestamp
        sorted_messages = sorted(
            messages,
            key=lambda m: m.created_at if m.created_at else datetime.min.replace(tzinfo=timezone.utc)
        )

        new_messages_found = 0
        for message in sorted_messages:
            # Check if message passes timestamp filter
            if messages_created_after and message.created_at:
                # If message.created_at is timezone-naive, assume it's UTC
                if message.created_at.tzinfo is None:
                    msg_timestamp = message.created_at.replace(tzinfo=timezone.utc).timestamp()
                else:
                    msg_timestamp = message.created_at.timestamp()
                if msg_timestamp < messages_created_after:
                    continue

            # Some message objects may not have an ID; skip them since we use IDs for dedupe.
            if not message.id:
                continue

            # Check if this is a new message or an update to existing message
            is_new_message = message.id not in seen_message_ids

            if yield_updates:
                # For streaming: track content changes
                # Use getattr to safely extract content and convert to string
                # This handles various content structures at runtime
                raw_content = getattr(message.content, 'content', message.content) if message.content else None
                content_str = str(raw_content) if raw_content is not None else ""

                # Ensure streaming_status is also properly converted to string
                streaming_status_str = str(message.streaming_status) if message.streaming_status is not None else ""
                content_hash = hash(content_str + streaming_status_str)
                is_updated = message.id in message_content_hashes and message_content_hashes[message.id] != content_hash

                if is_new_message or is_updated:
                    message_content_hashes[message.id] = content_hash
                    seen_message_ids.add(message.id)
                    new_messages_found += 1
                    yield message
            else:
                # Original behavior: only yield each message ID once
                if is_new_message:
                    seen_message_ids.add(message.id)
                    new_messages_found += 1
                    yield message

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
    queue: asyncio.Queue[dict[str, object] | None] = asyncio.Queue()
    stream_exc: BaseException | None = None

    async def consume_stream() -> None:
        nonlocal stream_exc
        try:
            async for event in stream_agent_response(
                client=client,
                task_id=task_id,
                timeout=timeout,
            ):
                await queue.put(event)
                if event.get("type") == "done":
                    break
        except BaseException as e:  # noqa: BLE001 - propagate after draining
            stream_exc = e
        finally:
            await queue.put(None)

    # Start consuming the stream *before* sending the event, so we don't block waiting for the first message.
    stream_task = asyncio.create_task(consume_stream())

    try:
        event_content = TextContentParam(type="text", author="user", content=user_message)
        await client.agents.send_event(agent_id=agent_id, params={"task_id": task_id, "content": event_content})

        while True:
            item = await queue.get()
            if item is None:
                break
            yield item

        if stream_exc is not None:
            raise stream_exc
    finally:
        if not stream_task.done():
            stream_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await stream_task


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
        raise
    except Exception as e:
        raise


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
