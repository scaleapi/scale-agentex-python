"""
Sample tests for AgentEx ACP agent.

This test suite demonstrates how to test the main AgentEx API functions:
- Non-streaming event sending and polling
- Streaming event sending

To run these tests:
1. Make sure the agent is running (via docker-compose or `agentex agents run`)
2. Set the AGENTEX_API_BASE_URL environment variable if not using default
3. Run: pytest test_agent.py -v

Configuration:
- AGENTEX_API_BASE_URL: Base URL for the AgentEx server (default: http://localhost:5003)
- AGENT_NAME: Name of the agent to test (default: ab080-batch-events)
"""

import os
import re
import uuid
import asyncio

import pytest
import pytest_asyncio
from test_utils.agentic import (
    stream_agent_response,
    send_event_and_poll_yielding,
)

from agentex import AsyncAgentex
from agentex.types import TaskMessage
from agentex.types.agent_rpc_params import ParamsCreateTaskRequest
from agentex.types.text_content_param import TextContentParam
from agentex.types.task_message_content import TextContent

# Configuration from environment variables
AGENTEX_API_BASE_URL = os.environ.get("AGENTEX_API_BASE_URL", "http://localhost:5003")
AGENT_NAME = os.environ.get("AGENT_NAME", "ab080-batch-events")


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
    """Test non-streaming event sending and polling."""

    @pytest.mark.asyncio
    async def test_send_event_and_poll(self, client: AsyncAgentex, agent_id: str):
        """Test sending a single event and polling for the response."""
        # Create a task for this conversation
        task_response = await client.agents.create_task(agent_id, params=ParamsCreateTaskRequest(name=uuid.uuid1().hex))
        task = task_response.result
        assert task is not None

        # Send an event and poll for response using the helper function
        # there should only be one message returned about batching
        async for message in send_event_and_poll_yielding(
            client=client,
            agent_id=agent_id,
            task_id=task.id,
            user_message="Process this single event",
            timeout=30,
            sleep_interval=1.0,
        ):
            assert isinstance(message, TaskMessage)
            assert isinstance(message.content, TextContent)
            assert "Processed event IDs" in message.content.content
            assert message.content.author == "agent"
            break

    @pytest.mark.asyncio
    async def test_send_multiple_events_batched(self, client: AsyncAgentex, agent_id: str):
        """Test sending multiple events that should be batched together."""
        # Create a task
        task_response = await client.agents.create_task(agent_id, params=ParamsCreateTaskRequest(name=uuid.uuid1().hex))
        task = task_response.result
        assert task is not None

        # Send multiple events in quick succession (should be batched)
        num_events = 7
        for i in range(num_events):
            event_content = TextContentParam(type="text", author="user", content=f"Batch event {i + 1}")
            await client.agents.send_event(agent_id=agent_id, params={"task_id": task.id, "content": event_content})
            await asyncio.sleep(0.1)  # Small delay to ensure ordering

        # Wait for processing to complete (5 events * 5 seconds each = 25s + buffer)

        ## there should be at least 2 agent responses to ensure that not all of the events are processed
        ## in the same message
        agent_messages = []
        async for message in send_event_and_poll_yielding(
            client=client,
            agent_id=agent_id,
            task_id=task.id,
            user_message="Process this single event",
            timeout=30,
            sleep_interval=1.0,
        ):
            if message.content and message.content.author == "agent":
                agent_messages.append(message)

            if len(agent_messages) == 2:
                break

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
    async def test_send_twenty_events_batched_streaming(self, client: AsyncAgentex, agent_id: str):
        """Test sending 20 events and verifying batch processing via streaming."""
        # Create a task
        task_response = await client.agents.create_task(agent_id, params=ParamsCreateTaskRequest(name=uuid.uuid1().hex))
        task = task_response.result
        assert task is not None

        # Send 10 events in quick succession (should be batched)
        num_events = 10
        print(f"\nSending {num_events} events in quick succession...")
        for i in range(num_events):
            event_content = TextContentParam(type="text", author="user", content=f"Batch event {i + 1}")
            await client.agents.send_event(agent_id=agent_id, params={"task_id": task.id, "content": event_content})
            await asyncio.sleep(0.1)  # Small delay to ensure ordering

        # Stream the responses and collect agent messages
        print("\nStreaming batch responses...")

        # We'll collect all agent messages from the stream
        agent_messages = []
        stream_timeout = 90  # Longer timeout for 20 events

        async for event in stream_agent_response(
            client=client,
            task_id=task.id,
            timeout=stream_timeout,
        ):
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
