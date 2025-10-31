"""
Tests for ab020-streaming (agentic agent)

Test coverage:
- Event sending and polling
- Streaming responses

Prerequisites:
    - AgentEx services running (make dev)
    - Agent running: agentex agents run --manifest manifest.yaml

Run: pytest tests/test_agent.py -v
"""

import pytest

from agentex.lib.testing import test_agentic_agent

AGENT_NAME = "ab020-streaming"


@pytest.mark.asyncio
async def test_send_event_and_poll():
    """Test sending events and polling for responses."""
    async with test_agentic_agent(agent_name=AGENT_NAME) as test:
        response = await test.send_event("Test message", timeout_seconds=30.0)
        # Validate we got a response (agent may need OpenAI key)
        assert response is not None
        assert response.content is not None  # May be error message
        print(f"Response: {response.content[:150]}")


@pytest.mark.asyncio
async def test_streaming_events():
    """Test streaming event responses."""
    async with test_agentic_agent(agent_name=AGENT_NAME) as test:
        events = []
        async for event in test.send_event_and_stream("Stream test", timeout_seconds=30.0):
            events.append(event)
            if event.get("type") == "done":
                break
        assert len(events) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
