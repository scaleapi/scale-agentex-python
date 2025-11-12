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
- AGENT_NAME: Name of the agent to test (default: s010-multiturn)
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
AGENT_NAME = os.environ.get("AGENT_NAME", "s010-multiturn")


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
        task_response = client.agents.create_task(agent_id, params=ParamsCreateTaskRequest(name=uuid.uuid1().hex))
        task = task_response.result

        assert task is not None

        messages = [
            "Hello, can you tell me a litle bit about tennis? I want to you make sure you use the word 'tennis' in each response.",
            "Pick one of the things you just mentioned, and dive deeper into it.",
            "Can you now output a summary of this conversation",
        ]

        for i, msg in enumerate(messages):
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
                validate_text_in_string("tennis", content.content)

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

    def test_stream_message(self, client: Agentex, agent_name: str, agent_id: str):
        """Test streaming messages in a multi-turn conversation."""

        # create a task for this specific conversation
        task_response = client.agents.create_task(agent_id, params=ParamsCreateTaskRequest(name=uuid.uuid1().hex))
        task = task_response.result

        assert task is not None
        messages = [
            "Hello, can you tell me a little bit about tennis? I want you to make sure you use the word 'tennis' in each response.",
            "Pick one of the things you just mentioned, and dive deeper into it.",
            "Can you now output a summary of this conversation",
        ]

        for i, msg in enumerate(messages):
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

            assert len(chunks) == 1
            # Get the actual content (prefer full_content if available, otherwise use aggregated)

            # Validate that "tennis" appears in the response because that is what our model does
            validate_text_in_string("tennis", aggregated_content)

            states = client.states.list(task_id=task.id)
            assert len(states) == 1

            message_history = client.messages.list(
                task_id=task.id,
            )
            assert len(message_history) == (i + 1) * 2  # user + agent messages


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
