"""Live integration tests for the sync Claude Code tutorial agent.

These tests require:
  - The agent running (via ``agentex agents run`` or docker-compose)
  - The ``claude`` CLI installed (``npm install -g @anthropic-ai/claude-code``)
  - ANTHROPIC_API_KEY set in the environment

To run:
    pytest tests/test_agent.py -v

For offline tests that do not need the CLI, see ``tests/test_agent_offline.py``.
"""

import os

import pytest
from test_utils.sync import collect_streaming_response

from agentex import Agentex
from agentex.types import TextContentParam
from agentex.types.agent_rpc_params import ParamsSendMessageRequest

AGENTEX_API_BASE_URL = os.environ.get("AGENTEX_API_BASE_URL", "http://localhost:5003")
AGENT_NAME = os.environ.get("AGENT_NAME", "s060-claude-code")


@pytest.fixture
def client():
    return Agentex(base_url=AGENTEX_API_BASE_URL)


@pytest.fixture
def agent_name():
    return AGENT_NAME


class TestStreamingMessages:
    """Live streaming tests -- needs the claude CLI + ANTHROPIC_API_KEY."""

    def test_stream_simple_message(self, client: Agentex, agent_name: str):
        """Stream a simple prompt through the local Claude Code subprocess."""
        stream = client.agents.send_message_stream(
            agent_name=agent_name,
            params=ParamsSendMessageRequest(
                content=TextContentParam(
                    author="user",
                    content="Reply with exactly three words: hello from claude",
                    type="text",
                )
            ),
        )
        aggregated_content, chunks = collect_streaming_response(stream)
        assert aggregated_content is not None
        assert len(chunks) >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
