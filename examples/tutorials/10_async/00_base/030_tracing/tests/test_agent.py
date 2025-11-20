"""
Tests for ab030-tracing (async agent)

This test suite demonstrates testing an async agent with tracing enabled.

Test coverage:
- Basic event sending and polling
- Streaming responses

Prerequisites:
    - AgentEx services running (make dev)
    - Agent running: agentex agents run --manifest manifest.yaml

Run tests:
    pytest tests/test_agent.py -v
"""

import pytest
import pytest_asyncio

from agentex.lib.testing import (
    async_test_agent,
    assert_valid_agent_response,
)
from agentex.lib.testing.sessions import AsyncAgentTest

AGENT_NAME = "ab030-tracing"


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
    """Test non-streaming event sending and polling."""

    @pytest.mark.asyncio
    async def test_send_event_and_poll(self, test_agent: AsyncAgentTest):
        """Test sending an event and polling for the response."""
        # Check for initial traces
        traces = await test_agent.client.spans.list(trace_id=test_agent.task_id)
        assert len(traces) == 0, "Should have no traces initially"

        # Send a test message and validate response
        response = await test_agent.send_event("Hello, this is a test message!", timeout_seconds=30.0)
        assert_valid_agent_response(response)

        # Check for traces after response
        traces = await test_agent.client.spans.list(trace_id=test_agent.task_id)
        assert len(traces) > 0, "Should have traces after sending event"
        traces_by_name = {trace.name: trace for trace in traces}
        assert "Turn 1" in traces_by_name, "Should have turn-based trace"
        assert "chat_completion_stream_auto_send" in traces_by_name, "Should have chat completion trace"
        assert "update_state" in traces_by_name, "Should have state update trace"


class TestStreamingEvents:
    """Test streaming event sending and response."""

    @pytest.mark.asyncio
    async def test_streaming_event(self, test_agent: AsyncAgentTest):
        """Test streaming events from agent."""
        # Check for initial traces
        traces = await test_agent.client.spans.list(trace_id=test_agent.task_id)
        assert len(traces) == 0, "Should have no traces initially"

        agent_response_found = False
        events_received = []
        async for event in test_agent.send_event_and_stream("Stream this", timeout_seconds=30.0):
            events_received.append(event)
            event_type = event.get("type")
            if event_type == "done":
                break

            elif event_type == "full":
                content = event.get("content", {})
                if content.get("content") is None:
                    continue  # Skip empty content

                if content.get("type") == "text" and content.get("author") == "agent":
                    # Check for agent response to user message
                    agent_response_found = True

            if agent_response_found:
                break

        assert len(events_received) > 0, "Should receive streaming events"
        # Check for traces after response
        traces = await test_agent.client.spans.list(trace_id=test_agent.task_id)
        assert len(traces) > 0, "Should have traces after sending event"
        traces_by_name = {trace.name: trace for trace in traces}
        assert "Turn 1" in traces_by_name, "Should have turn-based trace"
        assert "chat_completion_stream_auto_send" in traces_by_name, "Should have chat completion trace"
        assert "update_state" in traces_by_name, "Should have state update trace"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
