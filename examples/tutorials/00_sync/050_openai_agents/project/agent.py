"""OpenAI Agents SDK agent definition for the harness tutorial.

The agent is the boundary between this module and the API layer (acp.py).
The OpenAI Agents SDK runs its own tool-call loop internally; acp.py wraps a
``Runner.run_streamed`` result with ``OpenAITurn`` so it flows through the
unified harness surface.
"""

from __future__ import annotations

from datetime import datetime

from agents import Agent, function_tool, set_tracing_disabled

from project.tools import get_weather

# Disable the openai-agents SDK's native tracer so it doesn't ship traces to
# api.openai.com (the key may be a gateway/proxy key). Agentex tracing still
# runs via the harness + tracing manager configured in acp.py.
set_tracing_disabled(True)

MODEL_NAME = "gpt-4o"
INSTRUCTIONS = """You are a helpful AI assistant with access to tools.

Current date and time: {timestamp}

Guidelines:
- Be concise and helpful
- Use the weather tool when the user asks about the weather
- Always report the real tool output back to the user
"""


@function_tool
def weather(city: str) -> str:
    """Get the current weather for a city."""
    return get_weather(city)


def create_agent() -> Agent:
    """Build and return the OpenAI Agents SDK agent with the weather tool."""
    return Agent(
        name="Harness OpenAI Assistant",
        model=MODEL_NAME,
        instructions=INSTRUCTIONS.format(timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        tools=[weather],
    )
