"""
Sample tests for AgentEx ACP agent with Human-in-the-Loop workflow.

This test suite demonstrates how to test human-in-the-loop workflows:
- Non-streaming event sending and polling
- Detecting when workflow is waiting for human approval
- Sending Temporal signals to approve/reject
- Verifying workflow completes after approval

To run these tests:
1. Make sure the agent is running (via docker-compose or `agentex agents run`)
2. Make sure Temporal is running (localhost:7233)
3. Set the AGENTEX_API_BASE_URL environment variable if not using default
4. Run: pytest test_agent.py -v

Configuration:
- AGENTEX_API_BASE_URL: Base URL for the AgentEx server (default: http://localhost:5003)
- AGENT_NAME: Name of the agent to test (default: example-tutorial)
- TEMPORAL_ADDRESS: Temporal server address (default: localhost:7233)
"""

import os
import uuid
import asyncio

import pytest
import pytest_asyncio

# Temporal imports for signaling child workflows
from temporalio.client import Client as TemporalClient
from test_utils.async_utils import (
    poll_messages,
    send_event_and_poll_yielding,
)

from agentex import AsyncAgentex
from agentex.types.task_message import TaskMessage
from agentex.types.agent_rpc_params import ParamsCreateTaskRequest

# Configuration from environment variables
AGENTEX_API_BASE_URL = os.environ.get("AGENTEX_API_BASE_URL", "http://localhost:5003")
AGENT_NAME = os.environ.get("AGENT_NAME", "at080-open-ai-agents-sdk-human-in-the-loop")
TEMPORAL_ADDRESS = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")


@pytest_asyncio.fixture
async def client():
    """Create an AsyncAgentex client instance for testing."""
    client = AsyncAgentex(base_url=AGENTEX_API_BASE_URL)
    yield client
    await client.close()


@pytest_asyncio.fixture
async def temporal_client():
    """Create a Temporal client for sending signals to workflows."""
    client = await TemporalClient.connect(TEMPORAL_ADDRESS)
    yield client
    # Temporal client doesn't need explicit close in recent versions


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
    """Test non-streaming event sending and polling with human-in-the-loop."""

    @pytest.mark.asyncio
    async def test_send_event_and_poll_with_human_approval(self, client: AsyncAgentex, agent_id: str, temporal_client: TemporalClient):
        """Test sending an event that triggers human approval workflow."""
        # Create a task for this conversation
        task_response = await client.agents.create_task(agent_id, params=ParamsCreateTaskRequest(name=uuid.uuid1().hex))
        task = task_response.result
        assert task is not None

        # Poll for the initial task creation message
        task_creation_found = False
        async for message in poll_messages(
            client=client,
            task_id=task.id,
            timeout=30,
            sleep_interval=1.0,
        ):
            assert isinstance(message, TaskMessage)
            if message.content and message.content.type == "text" and message.content.author == "agent":
                # Check for the initial acknowledgment message
                assert "task" in message.content.content.lower() or "received" in message.content.content.lower()
                task_creation_found = True
                break

        assert task_creation_found, "Task creation message not found"

        # Send an event asking to confirm an order (triggers human-in-the-loop)
        user_message = "Please confirm my order"

        # Track what we've seen to ensure human-in-the-loop flow happened
        seen_tool_request = False
        seen_tool_response = False
        found_final_response = False
        approval_signal_sent = False

        async for message in send_event_and_poll_yielding(
            client=client,
            agent_id=agent_id,
            task_id=task.id,
            user_message=user_message,
            timeout=120,  # Longer timeout for human-in-the-loop
            sleep_interval=1.0,
            yield_updates=True,  # Get all streaming chunks
        ):
            assert isinstance(message, TaskMessage)

            # Track tool_request messages (agent calling wait_for_confirmation)
            if message.content and message.content.type == "tool_request":
                seen_tool_request = True

                if not approval_signal_sent:
                    # Send signal to child workflow to approve the order
                    # The child workflow ID is fixed as "child-workflow-id" (see tools.py)
                    # Give Temporal a brief moment to materialize the child workflow
                    await asyncio.sleep(1)
                    try:
                        handle = temporal_client.get_workflow_handle("child-workflow-id")
                        await handle.signal("fulfill_order_signal", True)
                        approval_signal_sent = True
                    except Exception as e:
                        # It's okay if the workflow completed before we could signal it.
                        _ = e

            # Track tool_response messages (child workflow completion)
            if message.content and message.content.type == "tool_response":
                seen_tool_response = True

            # Track agent text messages and their streaming updates
            if message.content and message.content.type == "text" and message.content.author == "agent":
                content_length = len(message.content.content) if message.content.content else 0

                # Stop when we get DONE status with actual content
                if message.streaming_status == "DONE" and content_length > 0:
                    found_final_response = True
                    break

        # Verify that we saw the complete flow: tool_request -> human approval -> tool_response -> final answer
        assert seen_tool_request, "Expected to see tool_request message (agent calling wait_for_confirmation)"
        assert seen_tool_response, "Expected to see tool_response message (child workflow completion after approval)"
        assert found_final_response, "Expected to see final text response after human approval"


class TestStreamingEvents:
    """Test streaming event sending (backend verification via polling)."""

    @pytest.mark.asyncio
    async def test_send_event_and_stream(self, client: AsyncAgentex, agent_id: str):
        """
        Streaming test placeholder.

        NOTE: SSE streaming is tested via the UI (agentex-ui subscribeTaskState).
        Backend streaming functionality is verified in test_send_event_and_poll_with_human_approval.
        """
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
