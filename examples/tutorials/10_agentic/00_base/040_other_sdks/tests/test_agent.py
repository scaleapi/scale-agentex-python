"""
Sample tests for AgentEx ACP agent with MCP servers and custom streaming.

This test suite demonstrates how to test agents that integrate:
- OpenAI Agents SDK with streaming
- MCP (Model Context Protocol) servers for tool access
- Custom streaming patterns (delta-based and full messages)
- Complex multi-turn conversations with tool usage

Key differences from regular streaming (020_streaming):
1. MCP Integration: Agent has access to external tools via MCP servers (sequential-thinking, web-search)
2. Tool Call Streaming: Tests both tool request and tool response streaming patterns
3. Mixed Streaming: Combines full message streaming (tools) with delta streaming (text)
4. Advanced State: Tracks turn_number and input_list instead of simple message history
5. Custom Streaming Context: Manual lifecycle management for different message types

To run these tests:
1. Make sure the agent is running (via docker-compose or `agentex agents run`)
2. Set the AGENTEX_API_BASE_URL environment variable if not using default
3. Ensure OPENAI_API_KEY is set in the environment
4. Run: pytest test_agent.py -v

Configuration:
- AGENTEX_API_BASE_URL: Base URL for the AgentEx server (default: http://localhost:5003)
- AGENT_NAME: Name of the agent to test (default: ab040-other-sdks)
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
from agentex.types.text_content_param import TextContentParam

# Configuration from environment variables
AGENTEX_API_BASE_URL = os.environ.get("AGENTEX_API_BASE_URL", "http://localhost:5003")
AGENT_NAME = os.environ.get("AGENT_NAME", "ab040-other-sdks")


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
    """Test non-streaming event sending and polling with MCP tools."""

    @pytest.mark.asyncio
    async def test_send_event_and_poll_simple_query(self, client: AsyncAgentex, agent_id: str):
        """Test sending a simple event and polling for the response (no tool use)."""
        # Create a task for this conversation
        task_response = await client.agents.create_task(agent_id, params=ParamsCreateTaskRequest(name=uuid.uuid1().hex))
        task = task_response.result
        assert task is not None

        # Check initial state - should have empty input_list and turn_number 0
        await asyncio.sleep(1)  # wait for state to be initialized
        states = await client.states.list(agent_id=agent_id, task_id=task.id)
        assert len(states) == 1

        state = states[0].state
        assert state is not None
        assert state.get("input_list", []) == []
        assert state.get("turn_number", 0) == 0

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

        # Verify state has been updated by polling the states for 10 seconds
        for i in range(10):
            if i == 9:
                raise Exception("Timeout waiting for state updates")
            states = await client.states.list(agent_id=agent_id, task_id=task.id)
            state = states[0].state
            if len(state.get("input_list", [])) > 0 and state.get("turn_number") == 1:
                break
            await asyncio.sleep(1)

        states = await client.states.list(agent_id=agent_id, task_id=task.id)
        state = states[0].state
        assert state.get("turn_number") == 1

    @pytest.mark.asyncio
    async def test_send_event_and_poll_with_tool_use(self, client: AsyncAgentex, agent_id: str):
        """Test sending an event that triggers tool usage and polling for the response."""
        # Create a task for this conversation
        task_response = await client.agents.create_task(agent_id, params=ParamsCreateTaskRequest(name=uuid.uuid1().hex))
        task = task_response.result
        assert task is not None

        # Send a message that should trigger the sequential-thinking tool
        user_message = "What is 15 multiplied by 37? Please think through this step by step."
        tool_request_found = False
        tool_response_found = False
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
            if message.content and message.content.type == "tool_request":
                tool_request_found = True
                assert message.content.author == "agent"
                assert hasattr(message.content, "name")
                assert hasattr(message.content, "tool_call_id")
            elif message.content and message.content.type == "tool_response":
                tool_response_found = True
                assert message.content.author == "agent"
            elif message.content and message.content.type == "text" and message.content.author == "agent":
                has_final_agent_response = True
                break

        assert has_final_agent_response, "Did not receive final agent text response"
        assert tool_request_found, "Did not see tool request message"
        assert tool_response_found, "Did not see tool response message"

    @pytest.mark.asyncio
    async def test_multi_turn_conversation_with_state(self, client: AsyncAgentex, agent_id: str):
        """Test multiple turns of conversation with state preservation."""
        # Create a task for this conversation
        task_response = await client.agents.create_task(agent_id, params=ParamsCreateTaskRequest(name=uuid.uuid1().hex))
        task = task_response.result
        assert task is not None

        # ensure the task is created before we send the first event
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

        ## keep polling the states for 10 seconds for the input_list and turn_number to be updated
        for i in range(30):
            if i == 29:
                raise Exception("Timeout waiting for state updates")
            states = await client.states.list(agent_id=agent_id, task_id=task.id)
            state = states[0].state
            if len(state.get("input_list", [])) > 0 and state.get("turn_number") == 1:
                break
            await asyncio.sleep(1)

        states = await client.states.list(agent_id=agent_id, task_id=task.id)
        state = states[0].state
        assert state.get("turn_number") == 1

        await asyncio.sleep(1)
        found_response = False
        # Second turn - reference previous context
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
                assert "blue" in response_text
                found_response = True
                break

        assert found_response, "Did not receive final agent text response"
        for i in range(10):
            if i == 9:
                raise Exception("Timeout waiting for state updates")
            states = await client.states.list(agent_id=agent_id, task_id=task.id)
            state = states[0].state
            if len(state.get("input_list", [])) > 0 and state.get("turn_number") == 2:
                break
            await asyncio.sleep(1)

        states = await client.states.list(agent_id=agent_id, task_id=task.id)
        state = states[0].state
        assert state.get("turn_number") == 2


class TestStreamingEvents:
    """Test streaming event sending with MCP tools and custom streaming patterns."""

    @pytest.mark.asyncio
    async def test_send_event_and_stream_simple(self, client: AsyncAgentex, agent_id: str):
        """Test streaming a simple response without tool usage."""
        # Create a task for this conversation
        task_response = await client.agents.create_task(agent_id, params=ParamsCreateTaskRequest(name=uuid.uuid1().hex))
        task = task_response.result
        assert task is not None

        # Check initial state
        await asyncio.sleep(1)  # wait for state to be initialized
        states = await client.states.list(agent_id=agent_id, task_id=task.id)
        assert len(states) == 1
        state = states[0].state
        assert state.get("input_list", []) == []
        assert state.get("turn_number", 0) == 0

        user_message = "Tell me a very short joke about programming."

        # Collect events from stream
        # Check for user message and delta messages
        user_message_found = False

        async def stream_messages() -> None:
            nonlocal user_message_found
            async for event in stream_agent_response(
                client=client,
                task_id=task.id,
                timeout=20,
            ):
                msg_type = event.get("type")
                # For full messages, content is at the top level
                # For delta messages, we need to check parent_task_message
                if msg_type == "full":
                    if event.get("content", {}).get("type") == "text" and event.get("content", {}).get("author") == "user":
                        user_message_found = True
                elif msg_type == "done":
                    break

        stream_task = asyncio.create_task(stream_messages())

        event_content = TextContentParam(type="text", author="user", content=user_message)
        await client.agents.send_event(agent_id=agent_id, params={"task_id": task.id, "content": event_content})

        # Wait for streaming to complete
        await stream_task
        assert user_message_found, "User message found in stream"
        ## keep polling the states for 10 seconds for the input_list and turn_number to be updated
        for i in range(10):
            if i == 9:
                raise Exception("Timeout waiting for state updates")
            states = await client.states.list(agent_id=agent_id, task_id=task.id)
            state = states[0].state
            if len(state.get("input_list", [])) > 0 and state.get("turn_number") == 1:
                break
            await asyncio.sleep(1)

        # Verify state has been updated
        states = await client.states.list(agent_id=agent_id, task_id=task.id)
        assert len(states) == 1
        state = states[0].state
        input_list = state.get("input_list", [])

        assert isinstance(input_list, list)
        assert len(input_list) >= 2
        assert state.get("turn_number") == 1

    @pytest.mark.asyncio
    async def test_send_event_and_stream_with_tools(self, client: AsyncAgentex, agent_id: str):
        """Test streaming with tool calls - demonstrates mixed streaming patterns."""
        # Create a task for this conversation
        task_response = await client.agents.create_task(agent_id, params=ParamsCreateTaskRequest(name=uuid.uuid1().hex))
        task = task_response.result
        assert task is not None

        # This query should trigger tool usage
        user_message = "Use sequential thinking to calculate what 123 times 456 equals."

        tool_requests_seen = []
        tool_responses_seen = []
        text_deltas_seen = []

        async def stream_messages() -> None:
            nonlocal tool_requests_seen, tool_responses_seen, text_deltas_seen

            async for event in stream_agent_response(
                client=client,
                task_id=task.id,
                timeout=45,
            ):
                msg_type = event.get("type")

                # For full messages, content is at the top level
                # For delta messages, we need to check parent_task_message
                if msg_type == "delta":
                    parent_msg = event.get("parent_task_message", {})
                    content = parent_msg.get("content", {})
                    delta = event.get("delta", {})
                    content_type = content.get("type")

                    if content_type == "text":
                        text_deltas_seen.append(delta.get("text_delta", ""))
                elif msg_type == "full":
                    # For full messages
                    content = event.get("content", {})
                    content_type = content.get("type")

                    if content_type == "tool_request":
                        tool_requests_seen.append(
                            {
                                "name": content.get("name"),
                                "tool_call_id": content.get("tool_call_id"),
                                "streaming_type": msg_type,
                            }
                        )
                    elif content_type == "tool_response":
                        tool_responses_seen.append(
                            {
                                "tool_call_id": content.get("tool_call_id"),
                                "streaming_type": msg_type,
                            }
                        )
                elif msg_type == "done":
                    break

        stream_task = asyncio.create_task(stream_messages())

        event_content = TextContentParam(type="text", author="user", content=user_message)
        await client.agents.send_event(agent_id=agent_id, params={"task_id": task.id, "content": event_content})

        # Wait for streaming to complete
        await stream_task

        # Verify we saw tool usage (if the agent decided to use tools)
        # Note: The agent may or may not use tools depending on its reasoning
        # Verify the state has a response written to it
        # assert len(text_deltas_seen) > 0, "Should have received text delta streaming"
        for i in range(10):
            if i == 9:
                raise Exception("Timeout waiting for state updates")
            states = await client.states.list(agent_id=agent_id, task_id=task.id)
            state = states[0].state
            if len(state.get("input_list", [])) > 0 and state.get("turn_number") == 1:
                break
            await asyncio.sleep(1)

        # Verify state has been updated
        states = await client.states.list(agent_id=agent_id, task_id=task.id)
        assert len(states) == 1
        state = states[0].state
        input_list = state.get("input_list", [])

        assert isinstance(input_list, list)
        assert len(input_list) >= 2
        print(input_list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
