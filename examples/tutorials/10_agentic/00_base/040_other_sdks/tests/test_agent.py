"""
Tests for ab040-other-sdks

Prerequisites:
    - AgentEx services running (make dev)
    - Agent running: agentex agents run --manifest manifest.yaml

Run: pytest tests/test_agent.py -v
"""
import asyncio

import pytest

from agentex import AsyncAgentex
from agentex.lib.testing import test_agentic_agent, assert_valid_agent_response

AGENT_NAME = "ab040-other-sdks"


@pytest.mark.asyncio
async def test_agent_basic():
    """Test basic agent functionality."""
    # Need client access to check state
    client = AsyncAgentex(api_key="test", base_url="http://localhost:5003")

    # Get agent ID
    agents = await client.agents.list()
    agent = next((a for a in agents if a.name == AGENT_NAME), None)
    assert agent is not None, f"Agent {AGENT_NAME} not found"

    async with test_agentic_agent(agent_name=AGENT_NAME) as test:
        # Wait for state initialization
        await asyncio.sleep(1)

        # Check initial state
        states = await client.states.list(agent_id=agent.id, task_id=test.task_id)
        assert len(states) == 1

        state = states[0].state
        assert state is not None
        assert state.get("input_list", []) == []
        assert state.get("turn_number", 0) == 0
        
        # Send simple message that shouldn't require tool use
        response = await test.send_event("Hello! Please introduce yourself briefly.", timeout_seconds=30.0)
        assert_valid_agent_response(response)

        # Wait for state update (agent may or may not update state with messages)
        await asyncio.sleep(2)

        # Check if state was updated
        states = await client.states.list(agent_id=agent.id, task_id=test.task_id)
        state = states[0].state
        assert state.get("turn_number") == 1


@pytest.mark.asyncio
async def test_poll_with_tool_use():
    """Test basic agent functionality."""
    # Need client access to check state
    client = AsyncAgentex(api_key="test", base_url="http://localhost:5003")

    # Get agent ID
    agents = await client.agents.list()
    agent = next((a for a in agents if a.name == AGENT_NAME), None)
    assert agent is not None, f"Agent {AGENT_NAME} not found"

    async with test_agentic_agent(agent_name=AGENT_NAME) as test:
        # Wait for state initialization
        await asyncio.sleep(1)

        # Check initial state
        states = await client.states.list(agent_id=agent.id, task_id=test.task_id)
        assert len(states) == 1

        state = states[0].state
        assert state is not None
        assert state.get("input_list", []) == []
        assert state.get("turn_number", 0) == 0
        
        # Send simple message that should trigger the sequential-thinking tool
        user_message = "What is 15 multiplied by 37? Please think through this step by step."
        tool_request_found = False
        tool_response_found = False

        response = await test.send_event(user_message, timeout_seconds=60.0)
        assert_valid_agent_response(response)

        # Check for tool use
        messages = await client.messages.list(task_id=test.task_id)
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
async def test_poll_multiturn():
    """Test basic agent functionality."""
    # Need client access to check state
    client = AsyncAgentex(api_key="test", base_url="http://localhost:5003")

    # Get agent ID
    agents = await client.agents.list()
    agent = next((a for a in agents if a.name == AGENT_NAME), None)
    assert agent is not None, f"Agent {AGENT_NAME} not found"

    async with test_agentic_agent(agent_name=AGENT_NAME) as test:
        # Wait for state initialization
        await asyncio.sleep(1)

        # Check initial state
        states = await client.states.list(agent_id=agent.id, task_id=test.task_id)
        assert len(states) == 1

        state = states[0].state
        assert state is not None
        assert state.get("input_list", []) == []
        assert state.get("turn_number", 0) == 0

        response = await test.send_event("My favorite color is blue", timeout_seconds=30.0)
        assert_valid_agent_response(response)

        second_response = await test.send_event("What did I just tell you my favorite color was?", timeout_seconds=30.0)
        assert_valid_agent_response(second_response)
        assert "blue" in second_response.content.lower()

        # Wait for state update (agent may or may not update state with messages)
        await asyncio.sleep(2)

        # Check if state was updated
        states = await client.states.list(agent_id=agent.id, task_id=test.task_id)
        state = states[0].state
        assert state.get("turn_number") == 2


@pytest.mark.asyncio
async def test_basic_streaming():
    """Test streaming event responses."""
    # Need client access to check state
    client = AsyncAgentex(api_key="test", base_url="http://localhost:5003")

    # Get agent ID
    agents = await client.agents.list()
    agent = next((a for a in agents if a.name == AGENT_NAME), None)
    assert agent is not None, f"Agent {AGENT_NAME} not found"

    async with test_agentic_agent(agent_name=AGENT_NAME) as test:
        # Wait for state initialization
        await asyncio.sleep(1)

        # Check initial state
        states = await client.states.list(agent_id=agent.id, task_id=test.task_id)
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

        # Stream events
        async for event in test.send_event_and_stream(user_message, timeout_seconds=30.0):
            events_received.append(event)
            event_type = event.get("type")

            if event_type == "done":
                done_delta_found = True
                break
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

        # Verify state has been updated
        await asyncio.sleep(1) # Wait for state update
        
        states = await client.states.list(agent_id=agent.id, task_id=test.task_id)
        assert len(states) == 1
        state = states[0].state
        input_list = state.get("input_list", [])
        assert isinstance(input_list, list)
        assert len(input_list) >= 2
        assert state.get("turn_number") == 1


@pytest.mark.asyncio
async def test_streaming_with_tools():
    """Test streaming event responses."""
    # Need client access to check state
    client = AsyncAgentex(api_key="test", base_url="http://localhost:5003")

    # Get agent ID
    agents = await client.agents.list()
    agent = next((a for a in agents if a.name == AGENT_NAME), None)
    assert agent is not None, f"Agent {AGENT_NAME} not found"

    async with test_agentic_agent(agent_name=AGENT_NAME) as test:
        # Wait for state initialization
        await asyncio.sleep(1)

        # Check initial state
        states = await client.states.list(agent_id=agent.id, task_id=test.task_id)
        assert len(states) == 1

        state = states[0].state
        assert state is not None
        assert state.get("input_list", []) == []
        assert state.get("turn_number", 0) == 0

        # This query should trigger tool usage
        user_message = "Use sequential thinking to calculate what 123 times 456 equals."

        events_received = []
        tool_request_found = False
        tool_response_found = False
        done_delta_found = False
        text_deltas_seen = []

        # Stream events
        async for event in test.send_event_and_stream(user_message, timeout_seconds=45.0):
            events_received.append(event)
            event_type = event.get("type")

            if event_type == "done":
                done_delta_found = True
                break
            elif event_type == "full":
                content = event.get("content", {})
                content_type = content.get("type")
                if content_type == "tool_request":
                    tool_request_found = True
                    assert content.get("author") == "agent"
                    assert "name" in content
                    assert "tool_call_id" in content
                elif content_type == "tool_response":
                    tool_response_found = True
                    assert content.get("author") == "agent"
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
        assert tool_request_found, "Should receive tool_request event"
        assert tool_response_found, "Should receive tool_response event"

        # Verify state has been updated
        await asyncio.sleep(1) # Wait for state update
        
        states = await client.states.list(agent_id=agent.id, task_id=test.task_id)
        assert len(states) == 1
        state = states[0].state
        input_list = state.get("input_list", [])
        assert isinstance(input_list, list)
        assert len(input_list) >= 2
        assert state.get("turn_number") == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
