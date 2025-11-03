"""
Sample tests for AgentEx Temporal State Machine agent.

This test suite demonstrates how to test a state machine-based agent that:
- Uses state transitions (WAITING → CLARIFYING → PERFORMING_DEEP_RESEARCH)
- Asks follow-up questions before performing research
- Performs deep web research using MCP servers
- Handles multi-turn conversations with context preservation

Key features tested:
1. State Machine Flow: Agent transitions through multiple states
2. Follow-up Questions: Agent clarifies queries before research
3. Deep Research: Agent performs extensive web research
4. Multi-turn Support: User can ask follow-ups about research

To run these tests:
1. Make sure the agent is running (via docker-compose or `agentex agents run`)
2. Set the AGENTEX_API_BASE_URL environment variable if not using default
3. Ensure OPENAI_API_KEY is set in the environment
4. Run: pytest test_agent.py -v

Configuration:
- AGENTEX_API_BASE_URL: Base URL for the AgentEx server (default: http://localhost:5003)
- AGENT_NAME: Name of the agent to test (default: at020-state-machine)
"""

import os
import uuid
import asyncio

import pytest
import pytest_asyncio
from test_utils.agentic import (
    stream_task_messages,
    send_event_and_poll_yielding,
)

from agentex import AsyncAgentex
from agentex.types.agent_rpc_params import ParamsCreateTaskRequest
from agentex.types.text_content_param import TextContentParam
from agentex.types.tool_request_content import ToolRequestContent

# Configuration from environment variables
AGENTEX_API_BASE_URL = os.environ.get("AGENTEX_API_BASE_URL", "http://localhost:5003")
AGENT_NAME = os.environ.get("AGENT_NAME", "at020-state-machine")


@pytest_asyncio.fixture
async def client():
    """Create an AsyncAgentex client instance for testing."""
    client = AsyncAgentex(base_url=AGENTEX_API_BASE_URL)
    yield client
    await client.close()


@pytest.fixture
def agent_name():
    """Return the agent name for testing."""
    return AGENT_NAME


@pytest_asyncio.fixture
async def agent_id(client, agent_name):
    """Retrieve the agent ID based on the agent name."""
    agents = await client.agents.list()
    for agent in agents:
        if agent.name == agent_name:
            return agent.id
    raise ValueError(f"Agent with name {agent_name} not found.")


class TestNonStreamingEvents:
    """Test non-streaming event sending and polling with state machine workflow."""
    @pytest.mark.asyncio
    async def test_send_event_and_poll_simple_query(self, client: AsyncAgentex, agent_id: str):
        """Test sending a simple event and polling for the response (no tool use)."""
        # Create a task for this conversation
        task_response = await client.agents.create_task(agent_id, params=ParamsCreateTaskRequest(name=uuid.uuid1().hex))
        task = task_response.result
        assert task is not None

        # Wait for workflow to initialize
        await asyncio.sleep(1)

        # Send a simple message that shouldn't require tool use
        user_message = "Hello! Please tell me the latest news about AI and AI startups."
        messages = []
        found_agent_message = False
        async for message in send_event_and_poll_yielding(
            client=client,
            agent_id=agent_id,
            task_id=task.id,
            user_message=user_message,
            timeout=30,
            sleep_interval=1.0,
        ):
            ## we should expect to get a question from the agent
            if message.content.type == "text" and message.content.author == "agent":
                found_agent_message = True
                break

        assert found_agent_message, "Did not find an agent message"

        # now we want to clarity that message
        await asyncio.sleep(2)
        next_user_message = "I want to know what viral news came up and which startups failed, got acquired, or became very successful or popular in the last 3 months"
        starting_deep_research_message = False
        uses_tool_requests = False
        async for message in send_event_and_poll_yielding(
            client=client,
            agent_id=agent_id,
            task_id=task.id,
            user_message=next_user_message,
            timeout=30,
            sleep_interval=1.0,
        ):
            if message.content.type == "text" and message.content.author == "agent":
                if "starting deep research" in message.content.content.lower():
                    starting_deep_research_message = True
            if isinstance(message.content, ToolRequestContent):
                uses_tool_requests = True
                break

        assert starting_deep_research_message, "Did not start deep research"
        assert uses_tool_requests, "Did not use tool requests"

class TestStreamingEvents:
    """Test streaming event sending with state machine workflow."""
    @pytest.mark.asyncio
    async def test_send_event_and_stream(self, client: AsyncAgentex, agent_id: str):
        """Test sending an event and streaming the response."""
        # Create a task for this conversation
        task_response = await client.agents.create_task(agent_id, params=ParamsCreateTaskRequest(name=uuid.uuid1().hex))
        task = task_response.result
        assert task is not None

        found_agent_message = False
        async def poll_message_in_background() -> None:
            nonlocal found_agent_message
            async for message in stream_task_messages(
                client=client,
                task_id=task.id,
                timeout=30,
            ):
                if message.content.type == "text" and message.content.author == "agent":
                    found_agent_message = True
                    break

            assert found_agent_message, "Did not find an agent message"

        poll_task = asyncio.create_task(poll_message_in_background())
        # create the first
        user_message = "Hello! Please tell me the latest news about AI and AI startups."
        await client.agents.send_event(agent_id=agent_id, params={"task_id": task.id, "content": TextContentParam(type="text", author="user", content=user_message)})

        await poll_task

        await asyncio.sleep(2)
        starting_deep_research_message = False
        uses_tool_requests = False
        async def poll_message_in_background_2() -> None:
            nonlocal starting_deep_research_message, uses_tool_requests
            async for message in stream_task_messages(
                client=client,
                task_id=task.id,
                timeout=30,
            ):
                # can you add the same checks as we did in the non-streaming events test?
                if message.content.type == "text" and message.content.author == "agent":
                    if "starting deep research" in message.content.content.lower():
                        starting_deep_research_message = True
                if isinstance(message.content, ToolRequestContent):
                    uses_tool_requests = True
                    break

            assert starting_deep_research_message, "Did not start deep research"
            assert uses_tool_requests, "Did not use tool requests"

        poll_task_2 = asyncio.create_task(poll_message_in_background_2())

        next_user_message = "I want to know what viral news came up and which startups failed, got acquired, or became very successful or popular in the last 3 months"
        await client.agents.send_event(agent_id=agent_id, params={"task_id": task.id, "content": TextContentParam(type="text", author="user", content=next_user_message)})
        await poll_task_2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
