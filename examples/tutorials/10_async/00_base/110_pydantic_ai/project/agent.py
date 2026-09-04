"""Pydantic AI agent definition for the async harness test agent.

The Agent is the boundary between this module and the API layer (acp.py).
Pydantic AI handles its own tool-call loop internally — no graph required.
"""

from __future__ import annotations

from datetime import datetime

from pydantic_ai import Agent

from project.tools import get_weather

__all__ = ["create_agent", "MODEL_NAME"]

MODEL_NAME = "openai:gpt-4o-mini"
SYSTEM_PROMPT = """You are a helpful AI assistant with access to tools.

Current date and time: {timestamp}

Guidelines:
- Be concise and helpful
- Use tools when they would help answer the user's question
- If you're unsure, ask clarifying questions
- Always provide accurate information
"""


def create_agent() -> Agent:
    """Build and return the Pydantic AI agent with tools registered."""
    agent = Agent(
        MODEL_NAME,
        system_prompt=SYSTEM_PROMPT.format(timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    )

    agent.tool_plain(get_weather)

    return agent
