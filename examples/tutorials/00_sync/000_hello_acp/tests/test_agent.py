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
- AGENT_NAME: Name of the agent to test (default: hello-acp)
"""

import os

import pytest

from agentex import Agentex
from agentex.types import TextDelta, TextContent, TextContentParam
from agentex.types.agent_rpc_params import ParamsSendMessageRequest
from agentex.types.task_message_update import StreamTaskMessageFull, StreamTaskMessageDelta

# Configuration from environment variables
AGENTEX_API_BASE_URL = os.environ.get("AGENTEX_API_BASE_URL", "http://localhost:5003")
AGENT_NAME = os.environ.get("AGENT_NAME", "s000-hello-acp")


@pytest.fixture
def client():
    """Create an AgentEx client instance for testing."""
    client = Agentex(base_url=AGENTEX_API_BASE_URL)
    yield client
    # Clean up: close the client connection
    client.close()


@pytest.fixture
def agent_name():
    """Return the agent name for testing."""
    return AGENT_NAME


class TestNonStreamingMessages:
    """Test non-streaming message sending."""

    def test_send_simple_message(self, client: Agentex, agent_name: str):
        """Test sending a simple message and receiving a response."""

        message_content = "Hello, Agent! How are you?"
        response = client.agents.send_message(
            agent_name=agent_name,
            params=ParamsSendMessageRequest(
                content=TextContentParam(
                    author="user",
                    content=message_content,
                    type="text",
                )
            ),
        )
        result = response.result
        assert result is not None
        assert len(result) == 1
        message = result[0]
        assert isinstance(message.content, TextContent)
        assert (
            message.content.content
            == f"Hello! I've received your message. Here's a generic response, but in future tutorials we'll see how you can get me to intelligently respond to your message. This is what I heard you say: {message_content}"
        )


class TestStreamingMessages:
    """Test streaming message sending."""

    def test_stream_simple_message(self, client: Agentex, agent_name: str):
        """Test streaming a simple message and aggregating deltas."""

        message_content = "Hello, Agent! Can you stream your response?"
        aggregated_content = ""
        full_content = ""
        received_chunks = False

        for chunk in client.agents.send_message_stream(
            agent_name=agent_name,
            params=ParamsSendMessageRequest(
                content=TextContentParam(
                    author="user",
                    content=message_content,
                    type="text",
                )
            ),
        ):
            received_chunks = True
            task_message_update = chunk.result
            # Collect text deltas as they arrive or check full messages
            if isinstance(task_message_update, StreamTaskMessageDelta) and task_message_update.delta is not None:
                delta = task_message_update.delta
                if isinstance(delta, TextDelta) and delta.text_delta is not None:
                    aggregated_content += delta.text_delta

            elif isinstance(task_message_update, StreamTaskMessageFull):
                content = task_message_update.content
                if isinstance(content, TextContent):
                    full_content = content.content

        if not full_content and not aggregated_content:
            raise AssertionError("No content was received in the streaming response.")
        if not received_chunks:
            raise AssertionError("No streaming chunks were received, when at least 1 was expected.")

        if full_content:
            assert (
                full_content
                == f"Hello! I've received your message. Here's a generic response, but in future tutorials we'll see how you can get me to intelligently respond to your message. This is what I heard you say: {message_content}"
            )

        if aggregated_content:
            assert (
                aggregated_content
                == f"Hello! I've received your message. Here's a generic response, but in future tutorials we'll see how you can get me to intelligently respond to your message. This is what I heard you say: {message_content}"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
