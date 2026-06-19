"""Tools for the LangGraph agent.

Tools are ``async`` so the in-workflow tool node can await them directly
(a sync tool would be offloaded via ``run_in_executor``, which Temporal's
workflow event loop does not allow).
"""

from __future__ import annotations

from langchain_core.tools import tool


@tool
async def get_weather(city: str) -> str:
    """Get the current weather for a city."""
    # TODO: replace with a real weather API call.
    return f"The weather in {city} is sunny and 72°F"


TOOLS = [get_weather]
