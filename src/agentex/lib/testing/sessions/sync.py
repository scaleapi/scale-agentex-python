"""
Sync Agent Testing

Provides testing utilities for sync agents that respond immediately via send_message().
"""

from __future__ import annotations

import logging
import uuid
from contextlib import contextmanager
from collections.abc import Generator

from agentex import Agentex
from agentex.types import Task, Agent
from agentex.types.task_message import TaskMessage
from agentex.types.text_content import TextContent
from agentex.types.message_author import MessageAuthor

logger = logging.getLogger(__name__)


class SyncAgentTest:
    """
    Test helper for sync agents that respond immediately.

    Sync agents use send_message() and should respond synchronously
    without requiring polling.
    """

    def __init__(self, client: Agentex, task: Task, agent: Agent):
        self.client = client
        self.task = task
        self.agent = agent
        self._conversation_history: list[TextContent] = []

    def send_message(self, content: str) -> TextContent:
        """
        Send message to sync agent and get immediate response.

        Args:
            content: Message text to send

        Returns:
            Agent's response as TextContent

        Note:
            Sync agents respond immediately. No async/await needed.
        """
        user_message = TextContent(author=MessageAuthor("user"), content=content)
        self._conversation_history.append(user_message)

        # Sync agents use send_message for immediate responses
        response = self.client.agents.send_message(task_id=self.task.id, content=user_message, agent_id=self.agent.id)

        # Extract response from TaskMessage
        if response and isinstance(response, TaskMessage) and response.content:
            agent_response = response.content
            if isinstance(agent_response, TextContent):
                self._conversation_history.append(agent_response)
                return agent_response

        raise RuntimeError(
            f"Sync agent {self.agent.id} did not provide immediate response. "
            f"Check agent configuration and AgentEx logs."
        )

    def get_conversation_history(self) -> list[TextContent]:
        """Get the full conversation history."""
        return self._conversation_history.copy()


@contextmanager
def sync_agent_test_session(
    agentex_client: Agentex,
) -> Generator[SyncAgentTest, None, None]:
    """
    Context manager for sync agent testing.

    Usage:
        with sync_agent_test_session(client) as test:
            response = test.send_message("Hello!")
            assert response is not None
    """
    task_name = f"sync-test-{uuid.uuid4().hex[:8]}"
    task: Task | None = None

    try:
        agents = agentex_client.agents.list()
        if not agents:
            raise RuntimeError("No agents registered. Run a tutorial agent first.")

        # Find sync agents
        sync_agents = [a for a in agents if a and hasattr(a, "acp_type") and a.acp_type == "sync"]

        if not sync_agents:
            agent = next((a for a in agents if a is not None), None)
            if not agent:
                raise RuntimeError("No valid agents available")
            logger.info("No sync agents found, using %s agent %s", agent.acp_type, agent.id)
        else:
            agent = sync_agents[0]

        # Create task
        task = agentex_client.agents.create_task(agent_id=agent.id, name=task_name, params={})

        yield SyncAgentTest(agentex_client, task, agent)

    finally:
        if task:
            try:
                agentex_client.tasks.delete(task_id=task.id)
            except Exception:
                pass  # Best effort cleanup


def test_sync_agent() -> Generator[SyncAgentTest, None, None]:
    """
    Simple sync agent testing without managing client.

    Usage:
        with test_sync_agent() as test:
            response = test.send_message("Hello!")
    """
    from agentex.lib.testing.fixtures import AGENTEX_BASE_URL

    client = Agentex(api_key="test", base_url=AGENTEX_BASE_URL)
    with sync_agent_test_session(client) as session:
        yield session
