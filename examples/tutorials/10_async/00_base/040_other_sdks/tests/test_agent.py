"""
Tests for ab040-other-sdks

Prerequisites:
    - AgentEx services running (make dev)
    - Agent running: agentex agents run --manifest manifest.yaml

Run: pytest tests/test_agent.py -v
"""

import asyncio

import pytest
import pytest_asyncio

from agentex.lib.testing import async_test_agent, stream_agent_response, assert_valid_agent_response
from agentex.lib.testing.sessions import AsyncAgentTest

AGENT_NAME = "ab040-other-sdks"


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
    """Test non-streaming event sending and polling with MCP tools."""

    @pytest.mark.asyncio
    async def test_send_event_and_poll_simple_query(self, test_agent: AsyncAgentTest):
        """Test basic agent functionality."""
        # Wait for state initialization
        await asyncio.sleep(1)

        # Check initial state
        states = await test_agent.client.states.list(agent_id=test_agent.agent.id, task_id=test_agent.task_id)
        assert len(states) == 1

        state = states[0].state
        assert state is not None
        assert state.get("input_list", []) == []
        assert state.get("turn_number", 0) == 0

        # Send a simple message that shouldn't require tool use
        response = await test_agent.send_event("Hello! Please introduce yourself briefly.", timeout_seconds=30.0)
        assert_valid_agent_response(response)

        # Wait for state update
        await asyncio.sleep(2)

        # Check if state was updated
        states = await test_agent.client.states.list(agent_id=test_agent.agent.id, task_id=test_agent.task_id)
        state = states[0].state
        assert state.get("turn_number") == 1

    @pytest.mark.asyncio
    async def test_send_event_and_poll_with_tool_use(self, test_agent: AsyncAgentTest):
        """Test basic agent functionality."""
        # Wait for state initialization
        await asyncio.sleep(1)

        # Check initial state
        states = await test_agent.client.states.list(agent_id=test_agent.agent.id, task_id=test_agent.task_id)
        assert len(states) == 1

        state = states[0].state
        assert state is not None
        assert state.get("input_list", []) == []
        assert state.get("turn_number", 0) == 0

        # Send a message that should trigger the sequential-thinking tool
        user_message = "What is 15 multiplied by 37? Please think through this step by step."
        tool_request_found = False
        tool_response_found = False

        response = await test_agent.send_event(user_message, timeout_seconds=60.0)
        assert_valid_agent_response(response)

        # Check for tool use
        messages = await test_agent.client.messages.list(task_id=test_agent.task_id)
        for msg in messages:
            if msg.content and msg.content.type == "tool_request":
                tool_request_found = True
                assert msg.content.author == "agent"
                assert hasattr(msg.content, "name")
                assert hasattr(msg.content, "tool_call_id")
            if msg.content and msg.content.type == "tool_response":
                tool_response_found = True
                assert msg.content.author == "agent"

        assert tool_request_found, "Expected tool_request message not found"
        assert tool_response_found, "Expected tool_response message not found"

    @pytest.mark.asyncio
    async def test_multi_turn_conversation_with_state(self, test_agent: AsyncAgentTest):
        """Test basic agent functionality."""
        # Wait for state initialization
        await asyncio.sleep(1)

        # Check initial state
        states = await test_agent.client.states.list(agent_id=test_agent.agent.id, task_id=test_agent.task_id)
        assert len(states) == 1

        state = states[0].state
        assert state is not None
        assert state.get("input_list", []) == []
        assert state.get("turn_number", 0) == 0

        response = await test_agent.send_event("My favorite color is blue", timeout_seconds=30.0)
        assert_valid_agent_response(response)

        second_response = await test_agent.send_event(
            "What did I just tell you my favorite color was?", timeout_seconds=30.0
        )
        assert_valid_agent_response(second_response)
        assert "blue" in second_response.content.lower()

        # Wait for state update (agent may or may not update state with messages)
        await asyncio.sleep(2)

        # Check if state was updated
        states = await test_agent.client.states.list(agent_id=test_agent.agent.id, task_id=test_agent.task_id)
        state = states[0].state
        assert state.get("turn_number") == 2


class TestStreamingEvents:
    """Test streaming event sending with MCP tools and custom streaming patterns."""

    @pytest.mark.asyncio
    async def test_send_event_and_stream_simple(self, test_agent: AsyncAgentTest):
        """Test streaming event responses."""
        # Wait for state initialization
        await asyncio.sleep(1)

        # Check initial state
        states = await test_agent.client.states.list(agent_id=test_agent.agent.id, task_id=test_agent.task_id)
        assert len(states) == 1

        state = states[0].state
        assert state is not None
        assert state.get("input_list", []) == []
        assert state.get("turn_number", 0) == 0

        # Send message and stream response
        user_message = "Tell me a very short joke about programming."

        events_received = []
        done_delta_found = False
        text_deltas_seen = []
        user_message_found = False

        # Stream events
        async for event in stream_agent_response(test_agent.client, test_agent.task_id, timeout=30.0):
            events_received.append(event)
            event_type = event.get("type")

            if event_type == "connected":
                await test_agent.send_event(user_message, timeout_seconds=30.0)

            if event_type == "done":
                done_delta_found = True
                break
            elif event_type == "full":
                content = event.get("content", {})
                content_type = content.get("type")
                if content_type == "text" and content.get("author") == "user":
                    user_message_found = True
            elif event_type == "delta":
                parent_msg = event.get("parent_task_message", {})
                content = parent_msg.get("content", {})
                delta = event.get("delta", {})
                content_type = content.get("type")

                if content_type == "text":
                    text_deltas_seen.append(delta.get("text_delta", ""))

        # Validate we received events
        assert len(events_received) > 0, "Should receive streaming events"
        assert len(text_deltas_seen) > 0, "Should receive delta agent message events"
        assert done_delta_found, "Should receive done event"
        assert user_message_found, "Should receive user message event"

        # Verify state has been updated
        await asyncio.sleep(1)  # Wait for state update

        states = await test_agent.client.states.list(agent_id=test_agent.agent.id, task_id=test_agent.task_id)
        assert len(states) == 1
        state = states[0].state
        input_list = state.get("input_list", [])
        assert isinstance(input_list, list)
        assert len(input_list) >= 2
        assert state.get("turn_number") == 1

    @pytest.mark.asyncio
    async def test_streaming_with_tools(self, test_agent: AsyncAgentTest):
        """Test streaming event responses."""
        # Wait for state initialization
        await asyncio.sleep(1)

        # Check initial state
        states = await test_agent.client.states.list(agent_id=test_agent.agent.id, task_id=test_agent.task_id)
        assert len(states) == 1

        state = states[0].state
        assert state is not None
        assert state.get("input_list", []) == []
        assert state.get("turn_number", 0) == 0

        # This query should trigger tool usage
        user_message = "Use sequential thinking to calculate what 123 times 456 equals."

        events_received = []
        tool_requests_seen = []
        tool_responses_seen = []
        text_deltas_seen = []

        # Stream events
        async for event in stream_agent_response(test_agent.client, test_agent.task_id, timeout=30.0):
            events_received.append(event)
            event_type = event.get("type")

            if event_type == "connected":
                await test_agent.send_event(user_message, timeout_seconds=30.0)

            elif event_type == "delta":
                parent_msg = event.get("parent_task_message", {})
                content = parent_msg.get("content", {})
                delta = event.get("delta", {})
                content_type = content.get("type")

                if content_type == "text":
                    text_deltas_seen.append(delta.get("text_delta", ""))
            elif event_type == "full":
                content = event.get("content", {})
                content_type = content.get("type")
                if content_type == "tool_request":
                    tool_requests_seen.append(
                        {
                            "name": content.get("name"),
                            "tool_call_id": content.get("tool_call_id"),
                            "streaming_type": event_type,
                        }
                    )
                elif content_type == "tool_response":
                    tool_responses_seen.append(
                        {
                            "tool_call_id": content.get("tool_call_id"),
                            "streaming_type": event_type,
                        }
                    )
            elif event_type == "done":
                break

        # Validate we received events
        assert len(events_received) > 0, "Should receive streaming events"
        assert len(text_deltas_seen) > 0, "Should receive delta agent message events"
        assert len(tool_requests_seen) > 0, "Should receive tool_request event"
        assert len(tool_responses_seen) > 0, "Should receive tool_response event"

        # Verify state has been updated
        await asyncio.sleep(1)  # Wait for state update

        states = await test_agent.client.states.list(agent_id=test_agent.agent.id, task_id=test_agent.task_id)
        assert len(states) == 1
        state = states[0].state
        input_list = state.get("input_list", [])
        assert isinstance(input_list, list)
        assert len(input_list) >= 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
