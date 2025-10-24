"""
Sync Agent Testing

Provides testing utilities for sync agents that respond immediately via send_message().
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from collections.abc import Generator

from agentex import Agentex
from agentex.types import Agent
from agentex.types.text_content import TextContent
from agentex.types.agent_rpc_params import ParamsSendMessageRequest

from agentex.lib.testing.config import config
from agentex.lib.testing.agent_selector import AgentSelector
from agentex.lib.testing.retry import with_retry
from agentex.lib.testing.exceptions import AgentResponseError
from agentex.lib.testing.type_utils import create_user_message, extract_agent_response

logger = logging.getLogger(__name__)


class SyncAgentTest:
    """
    Test helper for sync agents that respond immediately.

    Sync agents use send_message() and should respond synchronously
    without requiring polling or task management.
    """

    def __init__(self, client: Agentex, agent: Agent, task_id: str | None = None):
        self.client = client
        self.agent = agent
        self.task_id = task_id  # Optional task ID
        self._conversation_history: list[str] = []  # Store as strings
        self._task_name_counter = 0

    @with_retry
    def send_message(self, content: str) -> TextContent:
        """
        Send message to sync agent and get immediate response.

        Args:
            content: Message text to send

        Returns:
            Agent's response as TextContent

        Raises:
            AgentResponseError: If agent response is invalid
            Exception: Network or API errors (after retries)

        Note:
            Sync agents respond immediately. No async/await needed.
            Tasks are auto-created per conversation if not provided.
        """
        self._conversation_history.append(content)

        logger.debug(f"Sending message to sync agent {self.agent.id}: {content[:50]}...")

        # Create user message parameter
        user_message_param = create_user_message(content)

        # Build params - use task_id if we have one, otherwise auto-create
        if self.task_id:
            params = ParamsSendMessageRequest(task_id=self.task_id, content=user_message_param, stream=False)
        else:
            # Auto-create task with unique name
            self._task_name_counter += 1
            task_name = f"{config.task_name_prefix}-{self.agent.id[:8]}-{self._task_name_counter}"
            # Note: send_message might not support task_name auto-creation
            # We'll use task_id=None and let the API handle it
            params = ParamsSendMessageRequest(task_id=None, content=user_message_param, stream=False)

        # Sync agents use send_message for immediate responses
        response = self.client.agents.send_message(agent_id=self.agent.id, params=params)

        # Extract response using type_utils
        agent_response = extract_agent_response(response, self.agent.id)

        # Validate it's from agent
        if agent_response.author != "agent":
            raise AgentResponseError(
                self.agent.id,
                f"Expected author 'agent', got '{agent_response.author}'",
            )

        self._conversation_history.append(agent_response.content)

        logger.debug(f"Received response from agent: {agent_response.content[:50]}...")

        return agent_response

    def get_conversation_history(self) -> list[str]:
        """
        Get the full conversation history.

        Returns:
            List of message contents (strings) in chronological order
        """
        return self._conversation_history.copy()


@contextmanager
def sync_agent_test_session(
    agentex_client: Agentex,
    agent_name: str | None = None,
    agent_id: str | None = None,
    task_id: str | None = None,
) -> Generator[SyncAgentTest, None, None]:
    """
    Context manager for sync agent testing.

    Args:
        agentex_client: Agentex client instance
        agent_name: Agent name to test (required if agent_id not provided)
        agent_id: Agent ID to test (required if agent_name not provided)
        task_id: Optional task ID to use (if None, tasks auto-created)

    Yields:
        SyncAgentTest instance for testing

    Raises:
        AgentNotFoundError: No matching sync agents found
        AgentSelectionError: Multiple agents match, need to specify

    Usage:
        with sync_agent_test_session(client, agent_name="my-agent") as test:
            response = test.send_message("Hello!")
            assert response is not None
    """
    # Get all agents
    agents = agentex_client.agents.list()
    if not agents:
        from agentex.lib.testing.exceptions import AgentNotFoundError

        raise AgentNotFoundError("sync")

    # Select sync agent
    agent = AgentSelector.select_sync_agent(agents, agent_name, agent_id)

    # No task management needed - sync agents can auto-create or use provided task_id
    yield SyncAgentTest(agentex_client, agent, task_id)


def test_sync_agent(
    *, agent_name: str | None = None, agent_id: str | None = None
) -> Generator[SyncAgentTest, None, None]:
    """
    Simple sync agent testing without managing client.

    **Agent selection is required** - you must specify either agent_name or agent_id.

    Args:
        agent_name: Agent name to test (required if agent_id not provided)
        agent_id: Agent ID to test (required if agent_name not provided)

    Yields:
        SyncAgentTest instance for testing

    Raises:
        AgentSelectionError: Agent selection required or ambiguous
        AgentNotFoundError: No matching agent found

    Usage:
        with test_sync_agent(agent_name="my-agent") as test:
            response = test.send_message("Hello!")

    To discover agent names:
        Run: agentex agents list
    """
    client = Agentex(api_key="test", base_url=config.base_url)
    with sync_agent_test_session(client, agent_name, agent_id) as session:
        yield session
