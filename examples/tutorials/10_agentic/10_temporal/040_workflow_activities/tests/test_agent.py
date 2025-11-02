"""
Tests for Workflow Activities Tutorial.

This test suite demonstrates the workflow-level activities pattern:
- Agent processes messages (OpenAI Agents SDK)
- Workflow saves to database (activity)
- Workflow sends notifications (activity)
- Batch processing every 3 messages (activity)

To run these tests:
1. Make sure the agent is running (via `agentex agents run --manifest manifest.yaml`)
2. Set the AGENTEX_API_BASE_URL environment variable if not using default
3. Run: pytest test_agent.py -v

Configuration:
- AGENTEX_API_BASE_URL: Base URL for the AgentEx server (default: http://localhost:5003)
- AGENT_NAME: Name of the agent to test (default: workflow-activities-tutorial)
"""

import os
import uuid

import pytest
import pytest_asyncio
from test_utils.agentic import (
    poll_messages,
    send_event_and_poll_yielding,
)

from agentex import AsyncAgentex
from agentex.types.task_message import TaskMessage
from agentex.types.agent_rpc_params import ParamsCreateTaskRequest

# Configuration from environment variables
AGENTEX_API_BASE_URL = os.environ.get("AGENTEX_API_BASE_URL", "http://localhost:5003")
AGENT_NAME = os.environ.get("AGENT_NAME", "workflow-activities-tutorial")


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


class TestWorkflowActivities:
    """Test workflow-level activities alongside agent processing."""

    @pytest.mark.asyncio
    async def test_single_message_with_activities(self, client: AsyncAgentex, agent_id: str):
        """
        Test that a single message triggers:
        1. Agent processing (OpenAI Agents SDK)
        2. Database save activity
        3. Notification activity
        """
        # Create a task for this conversation
        task_response = await client.agents.create_task(agent_id, params=ParamsCreateTaskRequest(name=uuid.uuid1().hex))
        task = task_response.result
        assert task is not None

        # Poll for the initial welcome message
        print(f"[TEST] Polling for initial welcome message...")
        async for message in poll_messages(
            client=client,
            task_id=task.id,
            timeout=30,
            sleep_interval=1.0,
        ):
            if message.content and message.content.type == "text" and message.content.author == "agent":
                print(f"[TEST] Welcome message: {message.content.content[:80]}...")
                assert "Workflow Activities Tutorial" in message.content.content
                break

        # Send a message and track all messages
        user_message = "hi"
        print(f"[TEST] Sending message: '{user_message}'")

        seen_notification = False
        final_agent_message = None

        async for message in send_event_and_poll_yielding(
            client=client,
            agent_id=agent_id,
            task_id=task.id,
            user_message=user_message,
            timeout=60,
            sleep_interval=1.0,
            yield_updates=True,
        ):
            assert isinstance(message, TaskMessage)

            if not message.content:
                continue

            content = message.content.content or ""
            print(f"[TEST] Received - Type: {message.content.type}, Author: {message.content.author}, Status: {message.streaming_status}, Content: {content[:60]}...")

            # Track notification message (email notification from activity)
            if "[EMAIL]" in content and "Turn 1 completed" in content:
                print(f"[TEST] ✅ Saw notification activity message")
                seen_notification = True

            # Track agent text messages and save the final one
            if message.content.type == "text" and message.content.author == "agent" and "[EMAIL]" not in content:
                final_agent_message = message

                # Note when we get DONE status, but keep polling for notification
                if message.streaming_status == "DONE" and len(content) > 0:
                    print(f"[TEST] ✅ Agent streaming complete!")
                    # Don't break yet - continue polling for notification

        # Verify we got the agent response
        assert final_agent_message is not None, "Expected to see final agent message"
        assert final_agent_message.content is not None, "Final message should have content"
        assert len(final_agent_message.content.content) > 0, "Final message should have content"

        # If we didn't see notification during streaming, poll a bit more
        if not seen_notification:
            print(f"[TEST] Notification not seen yet, polling for a few more seconds...")
            async for message in poll_messages(
                client=client,
                task_id=task.id,
                timeout=5,
                sleep_interval=0.5,
            ):
                if message.content and "[EMAIL]" in message.content.content and "Turn 1 completed" in message.content.content:
                    print(f"[TEST] ✅ Saw notification activity message")
                    seen_notification = True
                    break

        # Verify we got the notification
        assert seen_notification, "Expected to see email notification from activity"

        print(f"[TEST] ✅ Test complete - agent responded and notification sent")

    @pytest.mark.asyncio
    async def test_batch_processing_after_three_messages(self, client: AsyncAgentex, agent_id: str):
        """
        Test that batch processing activity runs after 3 messages.
        """
        # Create a task
        task_response = await client.agents.create_task(agent_id, params=ParamsCreateTaskRequest(name=uuid.uuid1().hex))
        task = task_response.result
        assert task is not None

        # Skip welcome message
        async for message in poll_messages(client=client, task_id=task.id, timeout=30, sleep_interval=1.0):
            if message.content and "Workflow Activities Tutorial" in message.content.content:
                break

        # Send 3 messages and look for batch processing
        messages_to_send = ["tell me about life", "cool what else", "interesting"]
        seen_batch_processing = False

        for i, user_message in enumerate(messages_to_send, 1):
            print(f"\n[TEST] Sending message {i}/3: '{user_message}'")

            async for message in send_event_and_poll_yielding(
                client=client,
                agent_id=agent_id,
                task_id=task.id,
                user_message=user_message,
                timeout=60,
                sleep_interval=1.0,
                yield_updates=True,
            ):
                if not message.content:
                    continue

                content = message.content.content or ""

                # Look for batch processing messages
                if "Processing batch #1" in content:
                    print(f"[TEST] ✅ Batch processing started!")
                    seen_batch_processing = True

                if "Batch #1 complete" in content:
                    print(f"[TEST] ✅ Batch processing completed!")
                    # Found batch complete, we're done
                    break

                # Regular agent message - wait for DONE
                if (message.content.type == "text" and
                    message.content.author == "agent" and
                    message.streaming_status == "DONE" and
                    "[EMAIL]" not in content and
                    "batch" not in content.lower() and
                    len(content) > 10):
                    print(f"[TEST] ✅ Got agent response for message {i}")
                    break

            # If we saw batch complete, stop
            if seen_batch_processing and "Batch #1 complete" in content:
                break

        # Verify batch processing happened
        assert seen_batch_processing, "Expected to see batch processing after 3 messages"
        print(f"[TEST] ✅ Batch processing test complete!")


class TestStreamingEvents:
    """Test streaming event sending (backend verification via polling)."""

    @pytest.mark.asyncio
    async def test_send_event_and_stream(self, client: AsyncAgentex, agent_id: str):
        """
        Streaming test placeholder.

        NOTE: SSE streaming is tested via the UI (agentex-ui subscribeTaskState).
        Backend streaming functionality is verified in other tests.
        """
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
