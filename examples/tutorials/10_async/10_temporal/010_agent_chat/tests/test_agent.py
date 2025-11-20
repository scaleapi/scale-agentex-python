"""
Tests for at010-agent-chat (temporal agent)

Prerequisites:
    - AgentEx services running (make dev)
    - Temporal server running
    - Agent running: agentex agents run --manifest manifest.yaml

Key differences from base async (040_other_sdks):
1. Temporal Integration: Uses Temporal workflows for durable execution
2. State Management: State is managed within the workflow instance
3. No Race Conditions: Temporal ensures sequential event processing
4. Durable Execution: Workflow state survives restarts

Run: pytest tests/test_agent.py -v
"""

import asyncio

import pytest
import pytest_asyncio

from agentex.lib.testing import async_test_agent, stream_agent_response, assert_valid_agent_response
from agentex.lib.testing.sessions import AsyncAgentTest
from agentex.types.agent_rpc_result import StreamTaskMessageDone, StreamTaskMessageFull

AGENT_NAME = "at010-agent-chat"


@pytest.fixture
def agent_name():
    """Return the agent name for testing."""
    return AGENT_NAME


@pytest_asyncio.fixture
async def test_agent(agent_name: str):
    """Fixture to create a test async agent."""
    async with async_test_agent(agent_name=agent_name) as test:
        yield test

class TestNonStreamingEvents:
    """Test non-streaming event sending and polling with OpenAI Agents SDK."""

    @pytest.mark.asyncio
    async def test_send_event_and_poll_simple_query(self, test_agent: AsyncAgentTest):
        """Test basic agent functionality."""
        # Wait for state initialization
        await asyncio.sleep(1)

        # Send a simple message that shouldn't require tool use
        response = await test_agent.send_event("Hello! Please introduce yourself briefly.", timeout_seconds=30.0)
        assert_valid_agent_response(response)

    @pytest.mark.asyncio
    async def test_send_event_and_poll_with_calculator(self, test_agent: AsyncAgentTest):
        """Test sending an event that triggers calculator tool usage and polling for the response."""
        # Wait for workflow to initialize
        await asyncio.sleep(1)

        # Send a message that could trigger the calculator tool (though with reasoning, it may not need it)
        user_message = "What is 15 multiplied by 37?"
        response = await test_agent.send_event(user_message, timeout_seconds=60.0)
        assert_valid_agent_response(response)
        assert "555" in response.content, "Expected answer '555' not found in agent response"

    @pytest.mark.asyncio
    async def test_multi_turn_conversation_with_state(self, test_agent: AsyncAgentTest):
        """Test multiple turns of conversation with state preservation."""
        # Wait for workflow to initialize
        await asyncio.sleep(1)

        response = await test_agent.send_event("My favorite color is blue", timeout_seconds=30.0)
        assert_valid_agent_response(response)

        second_response = await test_agent.send_event(
            "What did I just tell you my favorite color was?", timeout_seconds=30.0
        )
        assert_valid_agent_response(second_response)
        assert "blue" in second_response.content.lower()


class TestStreamingEvents:
    """Test streaming event sending with OpenAI Agents SDK and tool usage."""

    @pytest.mark.asyncio
    async def test_send_event_and_stream_with_reasoning(self, test_agent: AsyncAgentTest):
        """Test streaming event responses."""
        # Wait for workflow to initialize
        await asyncio.sleep(1)

        # Send message and stream response
        user_message = "Tell me a very short joke about programming."

        # Check for user message and agent response
        user_message_found = False
        agent_response_found = False

        # Stream events
        async for event in stream_agent_response(test_agent.client, test_agent.task_id, timeout=60.0):
            event_type = event.get("type")

            if event_type == "connected":
                await test_agent.send_event(user_message, timeout_seconds=30.0)

            elif event_type == "full":
                task_message_update = StreamTaskMessageFull.model_validate(event)
                if task_message_update.parent_task_message and task_message_update.parent_task_message.id:
                    finished_message = await test_agent.client.messages.retrieve(task_message_update.parent_task_message.id)
                    if (
                        finished_message.content
                        and finished_message.content.type == "text"
                        and finished_message.content.author == "user"
                    ):
                        user_message_found = True
                    elif (
                        finished_message.content
                        and finished_message.content.type == "text"
                        and finished_message.content.author == "agent"
                    ):
                        agent_response_found = True
            elif event_type == "done":
                task_message_update = StreamTaskMessageDone.model_validate(event)
                if task_message_update.parent_task_message and task_message_update.parent_task_message.id:
                    finished_message = await test_agent.client.messages.retrieve(task_message_update.parent_task_message.id)
                    if finished_message.content and finished_message.content.type == "text" and finished_message.content.author == "agent":
                        agent_response_found = True
                continue

        assert user_message_found, "User message not found in stream"
        assert agent_response_found, "Agent response not found in stream"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
