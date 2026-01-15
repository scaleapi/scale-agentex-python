"""
Sample tests for AgentEx ACP agent.

This test suite demonstrates how to test the main AgentEx API functions:
- Non-streaming message sending
- Streaming message sending
- Task creation via RPC

To run these tests:
1. Make sure the agent is running (via docker-compose or `agentex agents run`)
2. Set the AGENTEX_API_BASE_URL environment variable if not using default
3. Run: pytest test_agent.py -v

Configuration:
- AGENTEX_API_BASE_URL: Base URL for the AgentEx server (default: http://localhost:5003)
- AGENT_NAME: Name of the agent to test (default: s020-streaming)
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
AGENT_NAME = os.environ.get("AGENT_NAME", "s020-streaming")


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
    """Test non-streaming message sending."""

    def test_send_message(self, client: Agentex, agent_name: str, agent_id: str):
        """
        Test message ordering by sending messages about distinct topics.

        This validates that the agent receives messages in chronological order.
        If messages are reversed (newest first), the agent would respond about
        the wrong topic.
        """
        task_response = client.agents.create_task(agent_id, params=ParamsCreateTaskRequest(name=uuid.uuid1().hex))
        task = task_response.result

        assert task is not None

        # Each message asks about a distinct topic with a required keyword in response
        # This validates message ordering: if order is wrong, agent responds about wrong topic
        messages_and_expected_keywords = [
            ("Tell me about tennis. You must include the word 'tennis' in your response.", "tennis"),
            ("Now tell me about basketball. You must include the word 'basketball' in your response. Do not mention tennis.", "basketball"),
            ("Now tell me about soccer. You must include the word 'soccer' in your response. Do not mention tennis or basketball.", "soccer"),
        ]

        for i, (msg, expected_keyword) in enumerate(messages_and_expected_keywords):
            response = client.agents.send_message(
                agent_name=agent_name,
                params=ParamsSendMessageRequest(
                    content=TextContentParam(
                        author="user",
                        content=msg,
                        type="text",
                    ),
                    task_id=task.id,
                ),
            )
            assert response is not None and response.result is not None
            result = response.result

            for message in result:
                content = message.content
                assert content is not None
                assert isinstance(content, TextContent) and isinstance(content.content, str)
                # Validate response contains the expected keyword for THIS message's topic
                validate_text_in_string(expected_keyword, content.content.lower())

            states = client.states.list(agent_id=agent_id, task_id=task.id)
            assert len(states) == 1

            state = states[0]
            assert state.state is not None
            assert state.state.get("system_prompt", None) == "You are a helpful assistant that can answer questions."
            message_history = client.messages.list(
                task_id=task.id,
            )
            assert len(message_history) == (i + 1) * 2  # user + agent messages


class TestStreamingMessages:
    """Test streaming message sending."""

    def test_send_stream_message(self, client: Agentex, agent_name: str, agent_id: str):
        """
        Test message ordering with streaming by sending messages about distinct topics.

        This validates that the agent receives messages in chronological order.
        If messages are reversed (newest first), the agent would respond about
        the wrong topic.
        """
        # create a task for this specific conversation
        task_response = client.agents.create_task(agent_id, params=ParamsCreateTaskRequest(name=uuid.uuid1().hex))
        task = task_response.result

        assert task is not None

        # Each message asks about a distinct topic with a required keyword in response
        # This validates message ordering: if order is wrong, agent responds about wrong topic
        messages_and_expected_keywords = [
            ("Tell me about tennis. You must include the word 'tennis' in your response.", "tennis"),
            ("Now tell me about basketball. You must include the word 'basketball' in your response. Do not mention tennis.", "basketball"),
            ("Now tell me about soccer. You must include the word 'soccer' in your response. Do not mention tennis or basketball.", "soccer"),
        ]

        for i, (msg, expected_keyword) in enumerate(messages_and_expected_keywords):
            stream = client.agents.send_message_stream(
                agent_name=agent_name,
                params=ParamsSendMessageRequest(
                    content=TextContentParam(
                        author="user",
                        content=msg,
                        type="text",
                    ),
                    task_id=task.id,
                ),
            )

            # Collect the streaming response
            aggregated_content, chunks = collect_streaming_response(stream)

            assert aggregated_content is not None
            # this is using the chat_completion_stream, so we will be getting chunks of data
            assert len(chunks) > 1, "No chunks received in streaming response."

            # Validate response contains the expected keyword for THIS message's topic
            validate_text_in_string(expected_keyword, aggregated_content.lower())

            states = client.states.list(agent_id=agent_id, task_id=task.id)
            assert len(states) == 1

            state = states[0]
            assert state.state is not None
            assert state.state.get("system_prompt", None) == "You are a helpful assistant that can answer questions."
            message_history = client.messages.list(
                task_id=task.id,
            )
            assert len(message_history) == (i + 1) * 2  # user + agent messages


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
