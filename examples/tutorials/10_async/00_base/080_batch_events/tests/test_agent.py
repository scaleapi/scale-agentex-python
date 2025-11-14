"""
Tests for ab080-batch-events

Prerequisites:
    - AgentEx services running (make dev)
    - Agent running: agentex agents run --manifest manifest.yaml

Run: pytest tests/test_agent.py -v
"""

import re
import asyncio

import pytest
import pytest_asyncio

from agentex.lib.testing import async_test_agent, stream_agent_response, assert_valid_agent_response
from agentex.lib.testing.sessions import AsyncAgentTest
from agentex.types.text_content_param import TextContentParam
from agentex.types.task_message_content import TextContent

AGENT_NAME = "ab080-batch-events"


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
        """Test sending a single event and polling for response."""
        response = await test_agent.send_event("Process this single event", timeout_seconds=30.0)
        assert_valid_agent_response(response)
        assert "Processed event IDs" in response.content


    @pytest.mark.asyncio
    async def test_batch_events_and_poll(self, test_agent: AsyncAgentTest):
        """Test sending events and polling for responses."""
        num_events = 7
        for i in range(num_events):
            event_content = TextContentParam(type="text", author="user", content=f"Batch event {i + 1}")
            await test_agent.client.agents.send_event(
                agent_id=test_agent.agent.id, params={"task_id": test_agent.task_id, "content": event_content}
            )
            await asyncio.sleep(0.1)  # Small delay to ensure ordering

        ## there should be at least 2 agent responses to ensure that not all of the events are processed
        await test_agent.send_event("Process this single event", timeout_seconds=30.0)
        # Wait for processing to complete (5 events * 5 seconds each = 25s + buffer)
        agent_messages = []
        for _ in range(8):
            agent_messages = await test_agent.client.messages.list(task_id=test_agent.task_id)
            if len(agent_messages) >= 2:
                break
            await asyncio.sleep(5)
        assert len(agent_messages) > 0, "Should have received at least one agent response"
        # PROOF OF BATCHING: Should have fewer responses than events sent
        assert len(agent_messages) < num_events, (
            f"Expected batching to result in fewer responses than {num_events} events, got {len(agent_messages)}"
        )

        # Analyze each batch response to count how many events were in each batch
        found_batch_with_multiple_events = False
        for msg in agent_messages:
            assert isinstance(msg.content, TextContent)
            response = msg.content.content
            # Count event IDs in this response (they're in a list like ['id1', 'id2', ...])
            # Use regex to find all quoted strings in the list
            event_ids = re.findall(r"'([^']+)'", response)
            batch_size = len(event_ids)
            if batch_size > 1:
                # this measn that we have found a batch with multiple events
                found_batch_with_multiple_events = True
                break

        assert found_batch_with_multiple_events, "Should have found a batch with multiple events"


class TestStreamingEvents:
    """Test streaming event sending."""

    @pytest.mark.asyncio
    async def test_batched_streaming(self, test_agent: AsyncAgentTest):
        """Test streaming responses."""
        num_events = 10
        for i in range(num_events):
            event_content = TextContentParam(type="text", author="user", content=f"Batch event {i + 1}")
            await test_agent.client.agents.send_event(
                agent_id=test_agent.agent.id, params={"task_id": test_agent.task_id, "content": event_content}
            )
            await asyncio.sleep(0.1)  # Small delay to ensure ordering

        # Stream events
        agent_messages = []
        async for event in stream_agent_response(test_agent.client, test_agent.task_id, timeout=30.0):
            # Collect agent text messages
            if event.get("type") == "full":
                content = event.get("content", {})
                if content.get("type") == "text" and content.get("author") == "agent":
                    msg_content = content.get("content", "")
                    if msg_content and msg_content.strip():
                        agent_messages.append(msg_content)

            if len(agent_messages) >= 2:
                break

        print(f"\nSent {num_events} events")
        print(f"Received {len(agent_messages)} agent response(s)")

        assert len(agent_messages) > 0, "Should have received at least one agent response"

        # PROOF OF BATCHING: Should have fewer responses than events sent
        assert len(agent_messages) < num_events, (
            f"Expected batching to result in fewer responses than {num_events} events, got {len(agent_messages)}"
        )

        # Analyze each batch response to count how many events were in each batch
        total_events_processed = 0
        found_batch_with_multiple_events = False
        for response in agent_messages:
            # Count event IDs in this response (they're in a list like ['id1', 'id2', ...])
            # Use regex to find all quoted strings in the list
            event_ids = re.findall(r"'([^']+)'", response)
            batch_size = len(event_ids)

            total_events_processed += batch_size

            # At least one response should have multiple events (proof of batching)
            if batch_size > 1:
                found_batch_with_multiple_events = True
                break

        assert found_batch_with_multiple_events, "Should have found a batch with multiple events"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
