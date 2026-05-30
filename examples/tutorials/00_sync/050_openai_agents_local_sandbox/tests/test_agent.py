"""Tests for the sync OpenAI Agents SDK local-sandbox agent.

This test suite validates:
- Sending a message that requires the agent to actually run a shell command in
  the LOCAL sandbox (unix_local backend) and receiving a non-empty response.

To run these tests:
1. Make sure the agent is running (via docker-compose or `agentex agents run`)
2. Set the AGENTEX_API_BASE_URL environment variable if not using default
3. Run: pytest test_agent.py -v

Configuration:
- AGENTEX_API_BASE_URL: Base URL for the AgentEx server (default: http://localhost:5003)
- AGENT_NAME: Name of the agent to test (default: s050-openai-agents-local-sandbox)
"""

import os

import pytest
from test_utils.sync import validate_text_in_string

from agentex import Agentex
from agentex.types import TextContentParam
from agentex.types.agent_rpc_params import ParamsSendMessageRequest

AGENTEX_API_BASE_URL = os.environ.get("AGENTEX_API_BASE_URL", "http://localhost:5003")
AGENT_NAME = os.environ.get("AGENT_NAME", "s050-openai-agents-local-sandbox")


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


def _response_text(result) -> str:
    """Flatten a send_message result into a single string for assertions.

    Result items may be a bare string, a ``TextContent`` (``.content`` is the
    string), or a ``TaskMessage`` wrapping a ``TextContent`` (``.content`` is the
    ``TextContent``, whose ``.content`` is the string). Dig through ``.content``
    until we reach a string.
    """

    def _text_of(obj, _depth: int = 0) -> str:
        if isinstance(obj, str):
            return obj
        if _depth > 5:
            return ""
        inner = getattr(obj, "content", None)
        if inner is None:
            return ""
        return _text_of(inner, _depth + 1)

    parts = [t for t in (_text_of(item) for item in result) if t]
    return "\n".join(parts)


class TestLocalSandboxMessages:
    """Test the local-sandbox OpenAI Agents SDK agent."""

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

    def test_shell_python_version(self, client: Agentex, agent_name: str):
        """Test that the agent uses its shell to run a real command.

        We ask it to print the Python version. The agent should run
        `python3 --version` in the local sandbox and report the real output,
        which always starts with "Python 3".
        """
        response = client.agents.send_message(
            agent_name=agent_name,
            params=ParamsSendMessageRequest(
                content=TextContentParam(
                    author="user",
                    content=(
                        "Use your shell to print the Python version on this "
                        "machine, then tell me what it is."
                    ),
                    type="text",
                )
            ),
        )
        result = response.result
        assert result is not None
        assert len(result) >= 1

        text = _response_text(result)
        assert text, "Expected a non-empty response from the sandbox agent."
        # The sandbox runs on Python 3.12, so the real output contains "Python 3".
        validate_text_in_string("Python 3", text)

    def test_shell_compute(self, client: Agentex, agent_name: str):
        """Test that the agent uses python3 in the sandbox to compute a value."""
        response = client.agents.send_message(
            agent_name=agent_name,
            params=ParamsSendMessageRequest(
                content=TextContentParam(
                    author="user",
                    content=(
                        "Use python3 in your shell to compute 21 * 2 and tell me "
                        "the result."
                    ),
                    type="text",
                )
            ),
        )
        result = response.result
        assert result is not None
        assert len(result) >= 1

        text = _response_text(result)
        assert text, "Expected a non-empty response from the sandbox agent."
        validate_text_in_string("42", text)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
