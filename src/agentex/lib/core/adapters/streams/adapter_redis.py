from __future__ import annotations

import os
import json
import asyncio
from typing import Any, Annotated, override
from collections.abc import AsyncIterator

import redis.asyncio as redis
from fastapi import Depends

from agentex.lib.utils.logging import make_logger
from agentex.lib.core.adapters.streams.port import StreamRepository

logger = make_logger(__name__)


_DEFAULT_STREAM_MAXLEN = 10000
_DEFAULT_STREAM_TTL_SECONDS = 3600


class RedisStreamRepository(StreamRepository):
    """
    A simplified Redis implementation of the EventStreamRepository interface.
    Optimized for text/JSON streaming with SSE.
    """

    def __init__(
        self,
        redis_url: str | None = None,
        stream_maxlen: int | None = None,
        stream_ttl_seconds: int | None = None,
    ):
        # Get Redis URL from environment if not provided
        self.redis_url = redis_url or os.environ.get(
            "REDIS_URL", "redis://localhost:6379"
        )
        self.redis = redis.from_url(self.redis_url)
        self.stream_maxlen = (
            stream_maxlen
            if stream_maxlen is not None
            else int(os.environ.get("REDIS_STREAM_MAXLEN", _DEFAULT_STREAM_MAXLEN))
        )
        # 0 disables sliding TTL.
        self.stream_ttl_seconds = (
            stream_ttl_seconds
            if stream_ttl_seconds is not None
            else int(
                os.environ.get("REDIS_STREAM_TTL_SECONDS", _DEFAULT_STREAM_TTL_SECONDS)
            )
        )

    @override
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

            # Pipeline XADD + EXPIRE in one round-trip so the stream key gets
            # a sliding TTL — orphaned streams (no writes for the TTL window)
            # self-delete. Mirrors the server-side adapter (scaleapi/scale-agentex#215).
            if self.stream_ttl_seconds > 0:
                async with self.redis.pipeline(transaction=False) as pipe:
                    pipe.xadd(
                        name=topic,
                        fields={"data": event_json},
                        maxlen=self.stream_maxlen,
                        approximate=True,
                    )
                    pipe.expire(name=topic, time=self.stream_ttl_seconds)
                    # raise_on_error=False so an EXPIRE failure does not surface
                    # to the caller after XADD already succeeded — that would
                    # risk callers retrying and duplicating messages. A failed
                    # TTL refresh is recoverable: MAXLEN still caps RAM and the
                    # next write resets the clock.
                    results = await pipe.execute(raise_on_error=False)
                    # results[0] = xadd message ID (or Exception)
                    # results[1] = expire bool (or Exception)
                    message_id = results[0]
                    if isinstance(message_id, Exception):
                        raise message_id
                    if isinstance(results[1], Exception):
                        logger.warning(
                            f"Failed to refresh TTL on stream {topic}: {results[1]}"
                        )
            else:
                message_id = await self.redis.xadd(
                    name=topic,
                    fields={"data": event_json},
                    maxlen=self.stream_maxlen,
                    approximate=True,
                )

            return message_id
        except Exception as e:
            logger.error(f"Error publishing to Redis stream {topic}: {e}")
            raise

    @override
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

    @override
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
