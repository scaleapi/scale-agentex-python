"""
Tests for at020-state-machine (temporal agent)

Prerequisites:
    - AgentEx services running (make dev)
    - Temporal server running
    - Agent running: agentex agents run --manifest manifest.yaml

Run: pytest tests/test_agent.py -v
"""

import asyncio

import pytest
import pytest_asyncio

from agentex.lib.testing import async_test_agent, stream_agent_response, assert_valid_agent_response
from agentex.lib.testing.sessions import AsyncAgentTest

AGENT_NAME = "at020-state-machine"



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
    """Test non-streaming event sending and polling with state machine workflow."""
    
    @pytest.mark.asyncio
    async def test_send_event_and_poll_simple_query(self, test_agent: AsyncAgentTest):
        """Test basic agent functionality."""
        # Wait for state initialization
        await asyncio.sleep(1)

        # Send a simple message that shouldn't require tool use
        response = await test_agent.send_event("Hello! Please tell me the latest news about AI and AI startups.", timeout_seconds=30.0)
        assert_valid_agent_response(response)

        # now we want to clarify that message
        await asyncio.sleep(2)
        next_user_message = "I want to know what viral news came up and which startups failed, got acquired, or became very successful or popular in the last 3 months"
        response = await test_agent.send_event(next_user_message, timeout_seconds=30.0)
        assert_valid_agent_response(response)
        assert "starting deep research" in response.content.lower(), "Did not start deep research"



class TestStreamingEvents:
    """Test streaming event sending with state machine workflow."""
    @pytest.mark.asyncio
    async def test_send_event_and_stream(self, test_agent: AsyncAgentTest):
        """Test sending an event and streaming the response."""
        # Wait for workflow to initialize
        await asyncio.sleep(1)

        # create the first message
        found_agent_message = False
        user_message = "Hello! Please tell me the latest news about AI and AI startups."
        async for event in test_agent.send_event_and_stream(user_message, timeout_seconds=30.0):
            content = event.get("content", {})
            if content.get("type") == "text" and content.get("author") == "agent":
                found_agent_message = True
                break

        await asyncio.sleep(2)
        starting_deep_research_message = False
        uses_tool_requests = False


        next_user_message = "I want to know what viral news came up and which startups failed, got acquired, or became very successful or popular in the last 3 months"
        # Stream events
        async for event in stream_agent_response(test_agent.client, test_agent.task_id, timeout=60.0):
            event_type = event.get("type")
            content = event.get("content", {})

            if event_type == "connected":
                await test_agent.send_event(next_user_message, timeout_seconds=30.0)

            if content.get("type") == "text" and content.get("author") == "agent":
                if "starting deep research" in content.get("content", "").lower():
                    starting_deep_research_message = True

            elif content.get("type") == "tool_request":
                # Check if we are using tool requests
                if content.get("author") == "agent":
                    uses_tool_requests = True

            if starting_deep_research_message and uses_tool_requests:
                break

        assert starting_deep_research_message, "Did not start deep research"
        assert uses_tool_requests, "Did not use tool requests"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
