"""
Tests for ab090-orchestrator-agent

Prerequisites:
    - AgentEx services running (make dev)
    - Agent running: agentex agents run --manifest manifest.yaml

Run: pytest tests/test_agent.py -v
"""

import pytest

from agentex.lib.testing import async_test_agent, assert_valid_agent_response

AGENT_NAME = "ab090-orchestrator-agent"


@pytest.mark.asyncio
async def test_agent_basic():
    """Test basic agent functionality."""
    async with async_test_agent(agent_name=AGENT_NAME) as test:
        response = await test.send_event("Test message", timeout_seconds=30.0)
        assert_valid_agent_response(response)


@pytest.mark.asyncio
async def test_agent_streaming():
    """Test streaming responses."""
    async with async_test_agent(agent_name=AGENT_NAME) as test:
        events = []
        async for event in test.send_event_and_stream("Stream test", timeout_seconds=30.0):
            events.append(event)
            if event.get("type") == "done":
                break
        assert len(events) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
