"""Tool definitions for the sync harness Pydantic AI agent.

Pydantic AI tools are registered directly on the Agent via decorators
(see project.agent). This module hosts the bare function so it is easy to
unit-test in isolation.
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
