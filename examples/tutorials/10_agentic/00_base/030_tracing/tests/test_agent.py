"""
Tests for ab030-tracing (agentic agent)

This test suite demonstrates testing an agentic agent with tracing enabled.

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

from agentex.lib.testing import (
    test_agentic_agent,
)

AGENT_NAME = "ab030-tracing"


@pytest.mark.asyncio
async def test_basic_event():
    """Test sending an event and receiving a response."""
    async with test_agentic_agent(agent_name=AGENT_NAME) as test:
        response = await test.send_event("Hello! Test message", timeout_seconds=30.0)
        # Agent may return empty response depending on configuration
        assert response is not None
        assert response.author == "agent"
        print(f"Response: {response.content[:100] if response.content else '(empty)'}")


@pytest.mark.asyncio
async def test_streaming_event():
    """Test streaming events from agent."""
    async with test_agentic_agent(agent_name=AGENT_NAME) as test:
        events_received = []

        async for event in test.send_event_and_stream("Stream this", timeout_seconds=30.0):
            events_received.append(event)
            if event.get("type") == "done":
                break

        assert len(events_received) > 0, "Should receive streaming events"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
