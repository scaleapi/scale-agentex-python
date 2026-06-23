"""Tool definitions for the harness_langgraph async agent."""

from langchain_core.tools import Tool


def get_weather(city: str) -> str:
    """Get the current weather for a city.

    Args:
        city: The name of the city to get weather for.

    Returns:
        A string describing the weather conditions.
    """
    return f"The weather in {city} is sunny and 72°F"


weather_tool = Tool(
    name="get_weather",
    func=get_weather,
    description="Get the current weather for a city. Input should be a city name.",
)

TOOLS = [weather_tool]
