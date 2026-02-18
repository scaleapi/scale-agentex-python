"""
Tests for the sync LangGraph agent.

This test suite validates:
- Non-streaming message sending with tool-calling LangGraph agent
- Streaming message sending with token-by-token output

To run these tests:
1. Make sure the agent is running (via docker-compose or `agentex agents run`)
2. Set the AGENTEX_API_BASE_URL environment variable if not using default
3. Run: pytest test_agent.py -v

Configuration:
- AGENTEX_API_BASE_URL: Base URL for the AgentEx server (default: http://localhost:5003)
- AGENT_NAME: Name of the agent to test (default: s030-langgraph)
"""

import os

import pytest
from test_utils.sync import validate_text_in_string, collect_streaming_response

from agentex import Agentex
from agentex.types import TextContent, TextContentParam
from agentex.types.agent_rpc_params import ParamsCreateTaskRequest, ParamsSendMessageRequest
from agentex.lib.sdk.fastacp.base.base_acp_server import uuid

# Configuration from environment variables
AGENTEX_API_BASE_URL = os.environ.get("AGENTEX_API_BASE_URL", "http://localhost:5003")
AGENT_NAME = os.environ.get("AGENT_NAME", "s030-langgraph")


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
    """Test non-streaming message sending with LangGraph agent."""

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

    def test_multiturn_conversation(self, client: Agentex, agent_name: str, agent_id: str):
        """Test multi-turn conversation with memory via LangGraph checkpointer."""
        task_response = client.agents.create_task(agent_id, params=ParamsCreateTaskRequest(name=uuid.uuid1().hex))
        task = task_response.result
        assert task is not None

        # First message
        response1 = client.agents.send_message(
            agent_name=agent_name,
            params=ParamsSendMessageRequest(
                content=TextContentParam(
                    author="user",
                    content="My name is Alice. Remember that.",
                    type="text",
                ),
                task_id=task.id,
            ),
        )
        assert response1.result is not None

        # Second message - agent should remember the name
        response2 = client.agents.send_message(
            agent_name=agent_name,
            params=ParamsSendMessageRequest(
                content=TextContentParam(
                    author="user",
                    content="What is my name?",
                    type="text",
                ),
                task_id=task.id,
            ),
        )
        assert response2.result is not None
        for message in response2.result:
            if isinstance(message.content, TextContent):
                validate_text_in_string("alice", message.content.content.lower())


class TestStreamingMessages:
    """Test streaming message sending with LangGraph agent."""

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
        """Test streaming with tool calls."""
        stream = client.agents.send_message_stream(
            agent_name=agent_name,
            params=ParamsSendMessageRequest(
                content=TextContentParam(
                    author="user",
                    content="What's the weather in New York?",
                    type="text",
                )
            ),
        )

        aggregated_content, chunks = collect_streaming_response(stream)

        assert aggregated_content is not None
        assert len(chunks) > 0, "No chunks received in streaming response."


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
