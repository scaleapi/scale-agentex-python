"""
Message Polling for Agentic Agents.

Provides efficient polling with exponential backoff and message ID tracking.
"""

from __future__ import annotations

import time
import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agentex import AsyncAgentex
    from agentex.types.text_content import TextContent
    from agentex.types.message_author import MessageAuthor

from agentex.lib.testing.config import config
from agentex.lib.testing.exceptions import AgentTimeoutError

logger = logging.getLogger(__name__)


class MessagePoller:
    """
    Polls for new messages from agentic agents with exponential backoff.

    Uses message IDs to track which messages have been seen, avoiding
    issues with object equality comparison.
    """

    def __init__(self, client: AsyncAgentex, task_id: str, agent_id: str):
        """
        Initialize message poller.

        Args:
            client: AsyncAgentex client instance
            task_id: Task ID to poll messages for
            agent_id: Agent ID for error messages
        """
        self.client = client
        self.task_id = task_id
        self.agent_id = agent_id
        self._seen_message_ids: set[str] = set()

    @staticmethod
    def _get_message_id(message) -> str | None:
        """
        Extract message ID from message object.

        Args:
            message: Message object

        Returns:
            Message ID if available, None otherwise
        """
        if hasattr(message, "id") and message.id:
            return str(message.id)
        return None

    async def poll_for_response(
        self,
        timeout_seconds: float,
        expected_author: MessageAuthor,
    ) -> TextContent:
        """
        Poll for new agent response with exponential backoff.

        Args:
            timeout_seconds: Maximum time to wait for response
            expected_author: Expected message author (e.g., MessageAuthor("agent"))

        Returns:
            New agent response as TextContent

        Raises:
            AgentTimeoutError: Agent didn't respond within timeout
        """
        from agentex.types.text_content import TextContent

        start_time = time.time()
        poll_interval = config.initial_poll_interval
        attempt = 0
        max_attempts = int(timeout_seconds / config.initial_poll_interval) * 2  # Reasonable max

        logger.debug(f"Starting to poll for agent response (task={self.task_id}, timeout={timeout_seconds}s)")

        while time.time() - start_time < timeout_seconds and attempt < max_attempts:
            attempt += 1

            try:
                # Fetch messages
                messages = await self.client.messages.list(task_id=self.task_id)

                # Find new agent messages
                new_agent_messages = []
                for msg in messages:
                    # Get message ID
                    msg_id = self._get_message_id(msg)
                    if msg_id is None:
                        logger.warning(f"Message without ID found: {msg}")
                        continue

                    # Skip if already seen
                    if msg_id in self._seen_message_ids:
                        continue

                    # Check if it's from expected author
                    if isinstance(msg.content, TextContent) and msg.content.author == expected_author:
                        new_agent_messages.append((msg_id, msg.content))

                # If we found new messages, return the most recent
                if new_agent_messages:
                    # Mark all new message IDs as seen
                    for msg_id, _ in new_agent_messages:
                        self._seen_message_ids.add(msg_id)

                    # Return the last (most recent) message
                    _, agent_response = new_agent_messages[-1]

                    elapsed = time.time() - start_time
                    logger.info(
                        f"Agent responded after {elapsed:.1f}s (attempt {attempt}): {agent_response.content[:50]}..."
                    )

                    return agent_response

                # Log progress periodically (every 3 attempts)
                if attempt % 3 == 0:
                    elapsed = time.time() - start_time
                    logger.debug(f"Still polling for response... (elapsed: {elapsed:.1f}s, attempt: {attempt})")

            except Exception as e:
                logger.warning(f"Error during polling attempt {attempt}: {e}")
                # Continue polling on errors (might be transient)

            # Wait before next poll with exponential backoff
            await asyncio.sleep(poll_interval)

            # Increase interval for next iteration (exponential backoff)
            poll_interval = min(poll_interval * config.poll_backoff_factor, config.max_poll_interval)

        # Timeout reached
        elapsed = time.time() - start_time
        logger.error(f"Agent did not respond within timeout (waited {elapsed:.1f}s, {attempt} attempts)")
        raise AgentTimeoutError(self.agent_id, timeout_seconds, self.task_id)

    def mark_messages_as_seen(self, messages) -> None:
        """
        Mark messages as seen to avoid processing them again.

        Args:
            messages: List of messages to mark as seen
        """
        for msg in messages:
            msg_id = self._get_message_id(msg)
            if msg_id:
                self._seen_message_ids.add(msg_id)
