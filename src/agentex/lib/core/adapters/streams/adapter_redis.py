import asyncio
import json
import os
from collections.abc import AsyncIterator
from typing import Annotated, Any

import redis.asyncio as redis
from fastapi import Depends

from agentex.lib.core.adapters.streams.port import StreamRepository
from agentex.lib.utils.logging import make_logger

logger = make_logger(__name__)


class RedisStreamRepository(StreamRepository):
    """
    A simplified Redis implementation of the EventStreamRepository interface.
    Optimized for text/JSON streaming with SSE.
    """

    def __init__(self, redis_url: str | None = None):
        # Get Redis URL from environment if not provided
        self.redis_url = redis_url or os.environ.get(
            "REDIS_URL", "redis://localhost:6379"
        )
        self.redis = redis.from_url(self.redis_url)

    async def send_event(self, topic: str, event: dict[str, Any]) -> str:
        """
        Send an event to a Redis stream.

        Args:
            topic: The stream topic/name
            event: The event data (will be JSON serialized)

        Returns:
            The message ID from Redis
        """
        try:
            # Simple JSON serialization
            event_json = json.dumps(event)

            # # Uncomment to debug
            # logger.info(f"Sending event to Redis stream {topic}: {event_json}")

            # Add to Redis stream with a reasonable max length
            message_id = await self.redis.xadd(
                name=topic,
                fields={"data": event_json},
            )

            return message_id
        except Exception as e:
            logger.error(f"Error publishing to Redis stream {topic}: {e}")
            raise

    async def subscribe(
        self, topic: str, last_id: str = "$"
    ) -> AsyncIterator[dict[str, Any]]:
        """
        Subscribe to a Redis stream and yield events as they come in.

        Args:
            topic: The stream topic to subscribe to
            last_id: Where to start reading from:
                    "$" = only new messages (default)
                    "0" = all messages from the beginning
                    "<id>" = messages after the specified ID

        Yields:
            Parsed event data
        """

        current_id = last_id

        while True:
            try:
                # Read new messages with a reasonable block time
                streams = {topic: current_id}
                response = await self.redis.xread(
                    streams=streams,
                    count=10,  # Get up to 10 messages at a time (reduces overprocessing)
                    block=2000,  # Wait up to 2 seconds for new messages
                )

                if response:
                    for _, messages in response:
                        for message_id, fields in messages:
                            # Update the last_id for next iteration
                            current_id = message_id

                            # Extract and parse the JSON data
                            if b"data" in fields:
                                try:
                                    data_str = fields[b"data"].decode("utf-8")
                                    event = json.loads(data_str)
                                    yield event
                                except Exception as e:
                                    logger.warning(
                                        f"Failed to parse event from Redis stream: {e}"
                                    )

                # Small sleep to prevent tight loops
                await asyncio.sleep(0.01)

            except Exception as e:
                logger.error(f"Error reading from Redis stream: {e}")
                await asyncio.sleep(1)  # Back off on errors

    async def cleanup_stream(self, topic: str) -> None:
        """
        Clean up a Redis stream.

        Args:
            topic: The stream topic to clean up
        """
        try:
            await self.redis.delete(topic)
            logger.info(f"Cleaned up Redis stream: {topic}")
        except Exception as e:
            logger.error(f"Error cleaning up Redis stream {topic}: {e}")
            raise


DRedisStreamRepository = Annotated[
    RedisStreamRepository | None, Depends(RedisStreamRepository)
]
