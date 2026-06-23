"""Tool definitions for the OpenAI Agents harness tutorial.

The bare function lives here so it's easy to unit-test; it's wrapped as an
OpenAI Agents SDK ``function_tool`` in ``project.agent``.
"""

from __future__ import annotations


def get_weather(city: str) -> str:
    """Get the current weather for a city.

    Args:
        city: The name of the city to get weather for.

    Returns:
        A string describing the weather conditions.
    """
    return f"The weather in {city} is sunny and 72°F"
