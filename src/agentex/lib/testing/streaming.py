"""
Streaming support for AgentEx Testing Framework.

Provides utilities for testing streaming responses from agents.
"""

from __future__ import annotations

import json
import asyncio
import logging
from typing import TYPE_CHECKING
from collections.abc import AsyncGenerator

if TYPE_CHECKING:
    from agentex import AsyncAgentex
    from agentex.types import TaskMessage


logger = logging.getLogger(__name__)


async def stream_agent_response(
    client: AsyncAgentex,
    task_id: str,
    timeout: float = 30.0,
) -> AsyncGenerator[dict, None]:
    """
    Stream agent response events as they arrive (SSE).

    Args:
        client: AsyncAgentex client
        task_id: Task ID to stream from
        timeout: Maximum seconds to wait (default: 30.0)

    Yields:
        Parsed event dictionaries from the SSE stream

    Example:
        async for event in stream_agent_response(client, task_id):
            if event.get('type') == 'delta':
                print(f"Delta: {event}")
            elif event.get('type') == 'done':
                print("Stream complete")
                break
    """
    try:
        async with asyncio.timeout(timeout):
            async with client.tasks.with_streaming_response.stream_events(task_id=task_id, timeout=timeout) as stream:
                async for line in stream.iter_lines():
                    if line.startswith("data: "):
                        # Parse SSE data
                        data = line.strip()[6:]  # Remove "data: " prefix
                        try:
                            event = json.loads(data)
                            yield event
                        except json.JSONDecodeError as e:
                            logger.warning(f"Failed to parse SSE event: {e}")
                            continue

    except asyncio.TimeoutError:
        logger.warning(f"Stream timed out after {timeout}s")
    except Exception as e:
        logger.error(f"Stream error: {e}")
        raise


async def stream_task_messages(
    client: AsyncAgentex,
    task_id: str,
    timeout: float = 30.0,
) -> AsyncGenerator[TaskMessage, None]:
    """
    Stream task messages as they arrive, parsing SSE events into TaskMessage objects.

    Args:
        client: AsyncAgentex client
        task_id: Task ID to stream from
        timeout: Maximum seconds to wait (default: 30.0)

    Yields:
        TaskMessage objects as they complete

    Example:
        async for message in stream_task_messages(client, task_id):
            if isinstance(message.content, TextContent):
                print(f"Message: {message.content.content}")
    """
    from agentex.types.agent_rpc_result import StreamTaskMessageDone, StreamTaskMessageFull

    async for event in stream_agent_response(client, task_id, timeout):
        msg_type = event.get("type")
        task_message = None

        if msg_type == "full":
            try:
                task_message_full = StreamTaskMessageFull.model_validate(event)
                if task_message_full.parent_task_message and task_message_full.parent_task_message.id:
                    finished_message = await client.messages.retrieve(task_message_full.parent_task_message.id)
                    task_message = finished_message
            except Exception as e:
                logger.warning(f"Failed to parse 'full' event: {e}")
                continue

        elif msg_type == "done":
            try:
                task_message_done = StreamTaskMessageDone.model_validate(event)
                if task_message_done.parent_task_message and task_message_done.parent_task_message.id:
                    finished_message = await client.messages.retrieve(task_message_done.parent_task_message.id)
                    task_message = finished_message
            except Exception as e:
                logger.warning(f"Failed to parse 'done' event: {e}")
                continue

        if task_message:
            yield task_message


def collect_streaming_deltas(stream_generator) -> tuple[str, list]:
    """
    Collect and aggregate streaming deltas from sync send_message.

    For sync agents using streaming mode.

    Args:
        stream_generator: Generator yielding SendMessageResponse chunks

    Returns:
        Tuple of (aggregated_content, list_of_chunks)

    Raises:
        AssertionError: If no chunks received or no content

    Example:
        response = client.agents.send_message(agent_id=..., params=..., stream=True)
        content, chunks = collect_streaming_deltas(response)
        assert "expected" in content
    """
    from agentex.types import TextDelta, TextContent
    from agentex.types.agent_rpc_result import StreamTaskMessageDone
    from agentex.types.task_message_update import StreamTaskMessageFull, StreamTaskMessageDelta

    aggregated_content = ""
    chunks = []

    for chunk in stream_generator:
        task_message_update = chunk.result
        chunks.append(chunk)

        # Collect text deltas as they arrive
        if isinstance(task_message_update, StreamTaskMessageDelta) and task_message_update.delta is not None:
            delta = task_message_update.delta
            if isinstance(delta, TextDelta) and delta.text_delta is not None:
                aggregated_content += delta.text_delta

        # Or collect full messages
        elif isinstance(task_message_update, StreamTaskMessageFull):
            content = task_message_update.content
            if isinstance(content, TextContent):
                aggregated_content = content.content

        elif isinstance(task_message_update, StreamTaskMessageDone):
            # Stream complete
            break

    # Validate we received something
    if not chunks:
        raise AssertionError("No streaming chunks were received")

    if not aggregated_content:
        raise AssertionError("No content was received in the streaming response")

    return aggregated_content, chunks
