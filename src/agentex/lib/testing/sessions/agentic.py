"""
Agentic Agent Testing

Provides testing utilities for agentic agents that use event-driven architecture
and require polling for responses.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from agentex import AsyncAgentex
from agentex.types import Task, Agent
from agentex.lib.testing.retry import with_async_retry
from agentex.lib.testing.config import config
from agentex.lib.testing.poller import MessagePoller
from agentex.types.text_content import TextContent
from agentex.lib.testing.type_utils import create_user_message
from agentex.types.agent_rpc_params import ParamsSendEventRequest
from agentex.lib.testing.task_manager import TaskManager
from agentex.lib.testing.agent_selector import AgentSelector

logger = logging.getLogger(__name__)


class AgenticAgentTest:
    """
    Test helper for agentic agents using event-driven architecture.

    Agentic agents use send_event() and require polling for async responses.
    """

    def __init__(self, client: AsyncAgentex, agent: Agent, task_id: str):
        self.client = client
        self.agent = agent
        self.task_id = task_id  # Required - must have a task
        self._conversation_history: list[str] = []  # Store as strings for simplicity
        self._poller = MessagePoller(client, task_id, agent.id)

    @with_async_retry
    async def send_event(self, content: str, timeout_seconds: float = 15.0) -> TextContent:
        """
        Send event to agentic agent and poll for response.

        Args:
            content: Message text to send
            timeout_seconds: Max time to wait for response (default: 15.0)

        Returns:
            Agent's response as TextContent

        Raises:
            AgentTimeoutError: Agent didn't respond within timeout
            Exception: Network or API errors (after retries)

        Note:
            Agentic agents respond asynchronously. This method polls for the response.
            Tasks are auto-created per conversation for simplicity.
        """
        self._conversation_history.append(content)

        logger.debug(f"Sending event to agentic agent {self.agent.id}: {content[:50]}...")

        # Create user message parameter
        user_message_param = create_user_message(content)

        # Build params with task_id
        params = ParamsSendEventRequest(task_id=self.task_id, content=user_message_param)

        # Send event (async, no immediate response)
        response = await self.client.agents.send_event(agent_id=self.agent.id, params=params)

        logger.debug("Event sent, polling for response...")

        # Poll for response using MessagePoller
        agent_response = await self._poller.poll_for_response(timeout_seconds=timeout_seconds, expected_author="agent")

        self._conversation_history.append(agent_response.content)

        return agent_response

    async def get_conversation_history(self) -> list[str]:
        """
        Get full conversation history.

        Returns:
            List of message contents (strings) in chronological order
        """
        return self._conversation_history.copy()


@asynccontextmanager
async def agentic_agent_test_session(
    agentex_client: AsyncAgentex,
    agent_name: str | None = None,
    agent_id: str | None = None,
    task_id: str | None = None,
) -> AsyncGenerator[AgenticAgentTest, None]:
    """
    Context manager for agentic agent testing.

    Args:
        agentex_client: AsyncAgentex client instance
        agent_name: Agent name to test (required if agent_id not provided)
        agent_id: Agent ID to test (required if agent_name not provided)
        task_id: Optional task ID to use (if None, creates a new task)

    Yields:
        AgenticAgentTest instance for testing

    Raises:
        AgentNotFoundError: No matching agentic agents found
        AgentSelectionError: Multiple agents match, need to specify

    Usage:
        # Auto-create task (recommended)
        async with agentic_agent_test_session(client, agent_name="my-agent") as test:
            response = await test.send_event("Hello!", timeout_seconds=15.0)

        # Use existing task
        async with agentic_agent_test_session(client, agent_name="my-agent", task_id="abc") as test:
            response = await test.send_event("Hello!", timeout_seconds=15.0)
    """
    task: Task | None = None

    try:
        # Get all agents
        agents = await agentex_client.agents.list()
        if not agents:
            from agentex.lib.testing.exceptions import AgentNotFoundError

            raise AgentNotFoundError("agentic")

        # Select agentic agent
        agent = AgentSelector.select_agentic_agent(agents, agent_name, agent_id)

        # Create task if not provided
        if not task_id:
            task = await TaskManager.create_task_async(agentex_client, agent, "agentic")
            task_id = task.id

        yield AgenticAgentTest(agentex_client, agent, task_id)

    finally:
        # Cleanup task if we created it
        if task:
            await TaskManager.cleanup_task_async(agentex_client, task.id, warn_on_failure=True)


@asynccontextmanager
async def test_agentic_agent(
    *, agent_name: str | None = None, agent_id: str | None = None, task_id: str | None = None
) -> AsyncGenerator[AgenticAgentTest, None]:
    """
    Simple agentic agent testing without managing client.

    **Agent selection is required** - you must specify either agent_name or agent_id.

    Args:
        agent_name: Agent name to test (required if agent_id not provided)
        agent_id: Agent ID to test (required if agent_name not provided)
        task_id: Optional task ID to use (if None, tasks auto-created)

    Yields:
        AgenticAgentTest instance for testing

    Raises:
        AgentSelectionError: Agent selection required or ambiguous
        AgentNotFoundError: No matching agent found

    Usage:
        async with test_agentic_agent(agent_name="my-agent") as test:
            response = await test.send_event("Hello!", timeout_seconds=15.0)

    To discover agent names:
        Run: agentex agents list
    """
    client = AsyncAgentex(api_key="test", base_url=config.base_url)
    async with agentic_agent_test_session(client, agent_name, agent_id, task_id) as session:
        yield session
