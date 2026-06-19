"""Tests for the sync Pydantic AI agent.

This test suite validates:
- Non-streaming message sending with tool-calling Pydantic AI agent
- Streaming message sending with token-by-token output

To run these tests:
1. Make sure the agent is running (via docker-compose or `agentex agents run`)
2. Set the AGENTEX_API_BASE_URL environment variable if not using default
3. Run: pytest test_agent.py -v

Configuration:
- AGENTEX_API_BASE_URL: Base URL for the AgentEx server (default: http://localhost:5003)
- AGENT_NAME: Name of the agent to test (default: s040-pydantic-ai)
"""

import os

import pytest
from test_utils.sync import validate_text_in_string, collect_streaming_response

from agentex import Agentex
from agentex.types import TextContentParam
from agentex.types.agent_rpc_params import ParamsSendMessageRequest

AGENTEX_API_BASE_URL = os.environ.get("AGENTEX_API_BASE_URL", "http://localhost:5003")
AGENT_NAME = os.environ.get("AGENT_NAME", "s040-pydantic-ai")


@pytest.fixture
def client():
    """Create an AgentEx client instance for testing."""
    return Agentex(base_url=AGENTEX_API_BASE_URL)


@pytest.fixture
def agent_name():
    """Return the agent name for testing."""
    return AGENT_NAME


@pytest.fixture
def agent_id(client, agent_name):
    """Retrieve the agent ID based on the agent name."""
    agents = client.agents.list()
    for agent in agents:
        if agent.name == agent_name:
            return agent.id
    raise ValueError(f"Agent with name {agent_name} not found.")


class TestNonStreamingMessages:
    """Test non-streaming message sending with Pydantic AI agent."""

    def test_send_simple_message(self, client: Agentex, agent_name: str):
        """Test sending a simple message and receiving a response."""
        response = client.agents.send_message(
            agent_name=agent_name,
            params=ParamsSendMessageRequest(
                content=TextContentParam(
                    author="user",
                    content="Hello! What can you help me with?",
                    type="text",
                )
            ),
        )
        result = response.result
        assert result is not None
        assert len(result) >= 1

    def test_tool_calling(self, client: Agentex, agent_name: str):
        """Test that the agent can use tools (e.g., weather tool)."""
        response = client.agents.send_message(
            agent_name=agent_name,
            params=ParamsSendMessageRequest(
                content=TextContentParam(
                    author="user",
                    content="What's the weather in San Francisco?",
                    type="text",
                )
            ),
        )
        result = response.result
        assert result is not None
        assert len(result) >= 1


class TestStreamingMessages:
    """Test streaming message sending with Pydantic AI agent."""

    def test_stream_simple_message(self, client: Agentex, agent_name: str):
        """Test streaming a simple message response."""
        stream = client.agents.send_message_stream(
            agent_name=agent_name,
            params=ParamsSendMessageRequest(
                content=TextContentParam(
                    author="user",
                    content="Tell me a short joke.",
                    type="text",
                )
            ),
        )

        aggregated_content, chunks = collect_streaming_response(stream)

        assert aggregated_content is not None
        assert len(chunks) > 1, "No chunks received in streaming response."

    def test_stream_tool_calling(self, client: Agentex, agent_name: str):
        """Test streaming with tool calls.

        This exercises the headline Pydantic AI converter feature:
        tool-call argument tokens streaming through as ToolRequestDelta.
        """
        stream = client.agents.send_message_stream(
            agent_name=agent_name,
            params=ParamsSendMessageRequest(
                content=TextContentParam(
                    author="user",
                    content="What's the weather in New York? Respond with the temperature.",
                    type="text",
                )
            ),
        )

        aggregated_content, chunks = collect_streaming_response(stream)

        assert aggregated_content is not None
        assert len(chunks) > 0, "No chunks received in streaming response."
        # The weather tool always returns "72°F", so the agent's reply should mention it.
        validate_text_in_string("72", aggregated_content)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
