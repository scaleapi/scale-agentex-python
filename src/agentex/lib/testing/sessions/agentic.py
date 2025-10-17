"""
Agentic Agent Testing

Provides testing utilities for agentic agents that use event-driven architecture
and require polling for responses.
"""
from __future__ import annotations

import time
import uuid
import asyncio
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from agentex import AsyncAgentex
from agentex.types import Task, Agent
from agentex.types.text_content import TextContent
from agentex.types.message_author import MessageAuthor


class AgenticAgentTest:
    """
    Test helper for agentic agents using event-driven architecture.

    Agentic agents use send_event() and require polling for async responses.
    """

    def __init__(self, client: AsyncAgentex, task: Task, agent: Agent):
        self.client = client
        self.task = task
        self.agent = agent
        self._conversation_history: list[TextContent] = []

    async def send_event(self, content: str, timeout_seconds: float = 15.0) -> TextContent:
        """
        Send event to agentic agent and poll for response.

        Args:
            content: Message text to send
            timeout_seconds: Max time to wait for response

        Returns:
            Agent's response as TextContent
        """
        user_message = TextContent(author=MessageAuthor("user"), content=content)
        self._conversation_history.append(user_message)

        # Send event (async, no immediate response)
        await self.client.agents.send_event(task_id=self.task.id, content=user_message, agent_id=self.agent.id)

        return await self._poll_for_response(timeout_seconds)

    async def _poll_for_response(self, timeout_seconds: float) -> TextContent:
        """Poll for agentic agent response."""
        start_time = time.time()
        poll_interval = 1.0

        while time.time() - start_time < timeout_seconds:
            # Get latest messages
            messages = await self.client.messages.list(task_id=self.task.id)

            # Find new agent messages
            agent_messages = [
                msg
                for msg in messages
                if (
                    isinstance(msg.content, TextContent)
                    and msg.content.author == MessageAuthor("agent")
                    and msg.content not in self._conversation_history
                )
            ]

            if agent_messages:
                agent_response = agent_messages[-1].content
                if isinstance(agent_response, TextContent):
                    self._conversation_history.append(agent_response)
                    return agent_response

            await asyncio.sleep(poll_interval)

        elapsed = time.time() - start_time
        raise RuntimeError(
            f"Agentic agent {self.agent.id} did not respond within {timeout_seconds}s "
            f"(waited {elapsed:.1f}s). Check AgentEx logs."
        )

    async def get_conversation_history(self) -> list[TextContent]:
        """Get full conversation history."""
        return self._conversation_history.copy()


@asynccontextmanager
async def agentic_agent_test_session(
    agentex_client: AsyncAgentex,
) -> AsyncGenerator[AgenticAgentTest, None]:
    """
    Context manager for agentic agent testing.

    Usage:
        async with agentic_agent_test_session(client) as test:
            response = await test.send_event("Hello!", timeout_seconds=15.0)
    """
    task_name = f"agentic-test-{uuid.uuid4().hex[:8]}"
    task: Task | None = None

    try:
        agents = await agentex_client.agents.list()
        if not agents:
            raise RuntimeError("No agents registered. Run a tutorial agent first.")

        # Find agentic agents
        agentic_agents = [a for a in agents if a and hasattr(a, "acp_type") and a.acp_type == "agentic"]

        if not agentic_agents:
            raise RuntimeError("No agentic agents available. Run an agentic tutorial agent first.")

        agent = agentic_agents[0]

        # Create task
        task = await agentex_client.agents.create_task(agent_id=agent.id, name=task_name, params={})

        yield AgenticAgentTest(agentex_client, task, agent)

    finally:
        if task:
            try:
                await agentex_client.tasks.delete(task_id=task.id)
            except Exception:
                pass


async def test_agentic_agent() -> AsyncGenerator[AgenticAgentTest, None]:
    """
    Simple agentic agent testing without managing client.

    Usage:
        async with test_agentic_agent() as test:
            response = await test.send_event("Hello!", timeout_seconds=15.0)
    """
    from agentex.lib.testing.fixtures import AGENTEX_BASE_URL

    client = AsyncAgentex(api_key="test", base_url=AGENTEX_BASE_URL)
    async with agentic_agent_test_session(client) as session:
        yield session
