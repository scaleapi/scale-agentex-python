"""OpenAI Agents SDK agent definition for the Temporal harness tutorial.

Same agent shape as the sync (060) and async (130) variants. Here the agent is
built and run inside a Temporal activity (see ``project.activities``); the
workflow stays deterministic and delegates the non-deterministic LLM run to that
activity, which delivers the turn via the unified harness surface.
"""

from __future__ import annotations

from datetime import datetime

from agents import Agent, function_tool, set_tracing_disabled

from project.tools import get_weather

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
