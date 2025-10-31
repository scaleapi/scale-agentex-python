"""
Tests for example-tutorial (OpenAI Agents SDK Tools)

Prerequisites:
    - AgentEx services running (make dev)
    - Temporal server running
    - Agent running: agentex agents run --manifest manifest.yaml

Run: pytest tests/test_agent.py -v
"""

import pytest

from agentex.lib.testing import test_agentic_agent, assert_valid_agent_response

AGENT_NAME = "example-tutorial"


@pytest.mark.asyncio
async def test_agent_basic():
    """Test basic agent functionality."""
    async with test_agentic_agent(agent_name=AGENT_NAME) as test:
        response = await test.send_event("Test message", timeout_seconds=60.0)
        assert_valid_agent_response(response)


@pytest.mark.asyncio
async def test_agent_streaming():
    """Test streaming responses."""
    async with test_agentic_agent(agent_name=AGENT_NAME) as test:
        events = []
        async for event in test.send_event_and_stream("Stream test", timeout_seconds=60.0):
            events.append(event)
            if event.get("type") == "done":
                break
        assert len(events) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
