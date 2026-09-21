"""Tool definitions for the Temporal harness Pydantic AI agent.

These functions are registered on the base Pydantic AI agent. When the agent
is wrapped in ``TemporalAgent``, each tool call becomes its own Temporal
activity automatically — independently retryable and observable.

Tools must be ``async`` because Pydantic AI's Temporal integration requires
it: non-async tools would run in threads, which is non-deterministic and
unsafe for Temporal replay.
"""

from __future__ import annotations


async def get_weather(city: str) -> str:
    """Get the current weather for a city.

    Args:
        city: The name of the city to get weather for.

    Returns:
        A string describing the weather conditions.
    """
    return f"The weather in {city} is sunny and 72°F"
