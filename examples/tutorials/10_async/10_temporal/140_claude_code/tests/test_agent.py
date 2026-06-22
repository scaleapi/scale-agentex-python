"""Live integration tests for the Temporal Claude Code tutorial agent.

These tests require:
  - Temporal server, the ACP server, and the Temporal worker all running
  - The ``claude`` CLI installed (``npm install -g @anthropic-ai/claude-code``)
  - ANTHROPIC_API_KEY set in the environment

To run:
    pytest tests/test_agent.py -v

For offline tests that do not need the CLI, see ``tests/test_agent_offline.py``.
"""

import os
import time

import pytest

from agentex import Agentex
from agentex.types import TextContentParam
from agentex.types.agent_rpc_params import ParamsSendEventRequest

AGENTEX_API_BASE_URL = os.environ.get("AGENTEX_API_BASE_URL", "http://localhost:5003")
AGENT_NAME = os.environ.get("AGENT_NAME", "at140-claude-code")


@pytest.fixture
def client():
    return Agentex(base_url=AGENTEX_API_BASE_URL)


@pytest.fixture
def agent_name():
    return AGENT_NAME


@pytest.fixture
def agent_id(client, agent_name):
    agents = client.agents.list()
    for agent in agents:
        if agent.name == agent_name:
            return agent.id
    raise ValueError(f"Agent {agent_name!r} not found.")


class TestTemporalMessages:
    """Live Temporal tests -- needs Temporal server + the claude CLI + ANTHROPIC_API_KEY."""

    def test_send_simple_message(self, client: Agentex, agent_id: str):
        """Create a task, send a message, and poll until a response appears."""
        task = client.tasks.create(agent_id=agent_id)
        task_id = task.id

        client.agents.send_event(
            agent_id=agent_id,
            params=ParamsSendEventRequest(
                task_id=task_id,
                content=TextContentParam(
                    author="user",
                    content="Reply with exactly three words: hello from claude",
                    type="text",
                ),
            ),
        )

        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            msgs = client.messages.list(task_id=task_id)
            agent_msgs = [m for m in msgs if getattr(m.content, "author", None) == "agent"]
            # Filter out the task-initialized welcome message
            response_msgs = [m for m in agent_msgs if "Task initialized" not in str(getattr(m.content, "content", ""))]
            if response_msgs:
                assert len(response_msgs) >= 1
                return
            time.sleep(3)

        raise AssertionError("No agent response received within 90 s")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
