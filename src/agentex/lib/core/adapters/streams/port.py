from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any


class StreamRepository(ABC):
    """
    Interface for event streaming repositories.
    Used to publish and subscribe to event streams.
    """

    @abstractmethod
    async def send_event(self, topic: str, event: dict[str, Any]) -> str:
        """
        Send an event to a stream.

        Args:
            topic: The stream topic/name
            event: The event data

        Returns:
            The message ID or other identifier
        """
        raise NotImplementedError

    @abstractmethod
    async def subscribe(
        self, topic: str, last_id: str = "$"
    ) -> AsyncIterator[dict[str, Any]]:
        """
        Subscribe to a stream and yield events as they come in.

        Args:
            topic: The stream topic to subscribe to
            last_id: Where to start reading from

        Yields:
            Event data
        """
        raise NotImplementedError

    @abstractmethod
    async def cleanup_stream(self, topic: str) -> None:
        """
        Clean up a stream.

        Args:
            topic: The stream topic to clean up
        """
        raise NotImplementedError
