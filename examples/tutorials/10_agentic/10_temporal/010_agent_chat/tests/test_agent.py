"""
Sample tests for AgentEx Temporal agent with OpenAI Agents SDK integration.

This test suite demonstrates how to test agents that integrate:
- OpenAI Agents SDK with streaming (via Temporal workflows)
- MCP (Model Context Protocol) servers for tool access
- Multi-turn conversations with state management
- Tool usage (calculator and web search via MCP)

Key differences from base agentic (040_other_sdks):
1. Temporal Integration: Uses Temporal workflows for durable execution
2. State Management: State is managed within the workflow instance
3. No Race Conditions: Temporal ensures sequential event processing
4. Durable Execution: Workflow state survives restarts

To run these tests:
1. Make sure the agent is running (via docker-compose or `agentex agents run`)
2. Set the AGENTEX_API_BASE_URL environment variable if not using default
3. Ensure OPENAI_API_KEY is set in the environment
4. Run: pytest test_agent.py -v

Configuration:
- AGENTEX_API_BASE_URL: Base URL for the AgentEx server (default: http://localhost:5003)
- AGENT_NAME: Name of the agent to test (default: at010-agent-chat)
"""

import os
import uuid
import asyncio

import pytest
import pytest_asyncio
from test_utils.agentic import (
    stream_agent_response,
    send_event_and_poll_yielding,
)

from agentex import AsyncAgentex
from agentex.types import TaskMessage, TextContent
from agentex.types.agent_rpc_params import ParamsCreateTaskRequest
from agentex.types.agent_rpc_result import StreamTaskMessageDone, StreamTaskMessageFull
from agentex.types.text_content_param import TextContentParam

# Configuration from environment variables
AGENTEX_API_BASE_URL = os.environ.get("AGENTEX_API_BASE_URL", "http://localhost:5003")
AGENT_NAME = os.environ.get("AGENT_NAME", "at010-agent-chat")


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
    """Test non-streaming event sending and polling with OpenAI Agents SDK."""

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
        user_message = "Hello! Please introduce yourself briefly."
        messages = []
        async for message in send_event_and_poll_yielding(
            client=client,
            agent_id=agent_id,
            task_id=task.id,
            user_message=user_message,
            timeout=30,
            sleep_interval=1.0,
        ):
            assert isinstance(message, TaskMessage)
            messages.append(message)

            if len(messages) == 1:
                assert message.content == TextContent(
                    author="user",
                    content=user_message,
                    type="text",
                )
                break

    @pytest.mark.asyncio
    async def test_send_event_and_poll_with_calculator(self, client: AsyncAgentex, agent_id: str):
        """Test sending an event that triggers calculator tool usage and polling for the response."""
        # Create a task for this conversation
        task_response = await client.agents.create_task(agent_id, params=ParamsCreateTaskRequest(name=uuid.uuid1().hex))
        task = task_response.result
        assert task is not None

        # Wait for workflow to initialize
        await asyncio.sleep(1)

        # Send a message that could trigger the calculator tool (though with reasoning, it may not need it)
        user_message = "What is 15 multiplied by 37?"
        has_final_agent_response = False

        async for message in send_event_and_poll_yielding(
            client=client,
            agent_id=agent_id,
            task_id=task.id,
            user_message=user_message,
            timeout=60,  # Longer timeout for tool use
            sleep_interval=1.0,
        ):
            assert isinstance(message, TaskMessage)
            if message.content and message.content.type == "text" and message.content.author == "agent":
                # Check that the answer contains 555 (15 * 37)
                if "555" in message.content.content:
                    has_final_agent_response = True
                    break

        assert has_final_agent_response, "Did not receive final agent text response with correct answer"

    @pytest.mark.asyncio
    async def test_multi_turn_conversation(self, client: AsyncAgentex, agent_id: str):
        """Test multiple turns of conversation with state preservation."""
        # Create a task for this conversation
        task_response = await client.agents.create_task(agent_id, params=ParamsCreateTaskRequest(name=uuid.uuid1().hex))
        task = task_response.result
        assert task is not None

        # Wait for workflow to initialize
        await asyncio.sleep(1)

        # First turn
        user_message_1 = "My favorite color is blue."
        async for message in send_event_and_poll_yielding(
            client=client,
            agent_id=agent_id,
            task_id=task.id,
            user_message=user_message_1,
            timeout=20,
            sleep_interval=1.0,
        ):
            assert isinstance(message, TaskMessage)
            if message.content and message.content.type == "text" and message.content.author == "agent" and message.content.content:
                break

        # Wait a bit for state to update
        await asyncio.sleep(2)

        # Second turn - reference previous context
        found_response = False
        user_message_2 = "What did I just tell you my favorite color was?"
        async for message in send_event_and_poll_yielding(
            client=client,
            agent_id=agent_id,
            task_id=task.id,
            user_message=user_message_2,
            timeout=30,
            sleep_interval=1.0,
        ):
            if message.content and message.content.type == "text" and message.content.author == "agent" and message.content.content:
                response_text = message.content.content.lower()
                assert "blue" in response_text, f"Expected 'blue' in response but got: {response_text}"
                found_response = True
                break

        assert found_response, "Did not receive final agent text response with context recall"


class TestStreamingEvents:
    """Test streaming event sending with OpenAI Agents SDK and tool usage."""

    @pytest.mark.asyncio
    async def test_send_event_and_stream_with_reasoning(self, client: AsyncAgentex, agent_id: str):
        """Test streaming a simple response without tool usage."""
        # Create a task for this conversation
        task_response = await client.agents.create_task(agent_id, params=ParamsCreateTaskRequest(name=uuid.uuid1().hex))
        task = task_response.result
        assert task is not None

        # Wait for workflow to initialize
        await asyncio.sleep(1)

        user_message = "Tell me a very short joke about programming."

        # Check for user message and agent response
        user_message_found = False
        agent_response_found = False

        async def stream_messages() -> None:  # noqa: ANN101
            nonlocal user_message_found, agent_response_found
            async for event in stream_agent_response(
                client=client,
                task_id=task.id,
                timeout=20,
            ):
                msg_type = event.get("type")
                if msg_type == "full":
                    task_message_update = StreamTaskMessageFull.model_validate(event)
                    if task_message_update.parent_task_message and task_message_update.parent_task_message.id:
                        finished_message = await client.messages.retrieve(task_message_update.parent_task_message.id)
                        if finished_message.content and finished_message.content.type == "text" and finished_message.content.author == "user":
                            user_message_found = True
                        elif finished_message.content and finished_message.content.type == "text" and finished_message.content.author == "agent":
                            agent_response_found = True
                        elif finished_message.content and finished_message.content.type == "reasoning":
                            tool_response_found = True
                elif msg_type == "done":
                    task_message_update = StreamTaskMessageDone.model_validate(event)
                    if task_message_update.parent_task_message and task_message_update.parent_task_message.id:
                        finished_message = await client.messages.retrieve(task_message_update.parent_task_message.id)
                        if finished_message.content and finished_message.content.type == "reasoning":
                            agent_response_found = True
                    continue

        stream_task = asyncio.create_task(stream_messages())

        event_content = TextContentParam(type="text", author="user", content=user_message)
        await client.agents.send_event(agent_id=agent_id, params={"task_id": task.id, "content": event_content})

        # Wait for streaming to complete
        await stream_task

        assert user_message_found, "User message not found in stream"
        assert agent_response_found, "Agent response not found in stream"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
