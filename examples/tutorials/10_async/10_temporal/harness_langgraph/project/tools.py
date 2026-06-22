"""Tool definitions for the harness_langgraph temporal agent."""

from langchain_core.tools import Tool


def get_weather(city: str) -> str:
    """Get the current weather for a city.

    Args:
        city: The name of the city to get weather for.

    Returns:
        A string describing the weather conditions.
    """
    return f"The weather in {city} is sunny and 72°F"


async def aget_weather(city: str) -> str:
    """Native async tool entrypoint.

    ``tools_node`` runs inline in the Temporal workflow and invokes tools via
    ``tool.ainvoke``. A sync-only tool forces LangChain to bridge through
    ``run_in_executor`` (a thread pool), which the deterministic Temporal
    workflow event loop forbids (``NotImplementedError``). Providing a real
    coroutine keeps tool execution on the workflow loop.
    """
    return get_weather(city)


weather_tool = Tool(
    name="get_weather",
    func=get_weather,
    coroutine=aget_weather,
    description="Get the current weather for a city. Input should be a city name.",
)

TOOLS = [weather_tool]
