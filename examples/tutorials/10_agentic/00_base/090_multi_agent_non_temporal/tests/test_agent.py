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
- AGENT_NAME: Name of the agent to test (default: ab090-orchestrator-agent)
"""

import os
import uuid

import pytest
import pytest_asyncio
from test_utils.agentic import (
    stream_agent_response,
    send_event_and_poll_yielding,
)

from agentex import AsyncAgentex
from agentex.types.agent_rpc_params import ParamsCreateTaskRequest
from agentex.types.text_content_param import TextContentParam

# Configuration from environment variables
AGENTEX_API_BASE_URL = os.environ.get("AGENTEX_API_BASE_URL", "http://localhost:5003")
AGENT_NAME = os.environ.get("AGENT_NAME", "ab090-orchestrator-agent")


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
    async def test_multi_agent_workflow_complete(self, client: AsyncAgentex, agent_id: str):
        """Test the complete multi-agent workflow with all agents using polling that yields messages."""
        # Create a task for the orchestrator
        task_response = await client.agents.create_task(agent_id, params=ParamsCreateTaskRequest(name=uuid.uuid1().hex))
        task = task_response.result
        assert task is not None

        # Send a content creation request as JSON
        request_json = {
            "request": "Write a welcome message for our AI assistant",
            "rules": ["Under 50 words", "Friendly tone", "Include emoji"],
            "target_format": "HTML",
        }

        import json

        # Collect messages as they arrive from polling
        messages = []
        print("\n🔄 Polling for multi-agent workflow responses...")

        # Track which agents have completed their work
        workflow_markers = {
            "orchestrator_started": False,
            "creator_called": False,
            "critic_called": False,
            "formatter_called": False,
            "workflow_completed": False,
        }

        all_agents_done = False
        async for message in send_event_and_poll_yielding(
            client=client,
            agent_id=agent_id,
            task_id=task.id,
            user_message=json.dumps(request_json),
            timeout=120,  # Longer timeout for multi-agent workflow
            sleep_interval=2.0,
        ):
            messages.append(message)
            # Print messages as they arrive to show real-time progress
            if message.content and message.content.content:
                # Track agent participation as messages arrive
                content = message.content.content.lower()

                if "starting content workflow" in content:
                    workflow_markers["orchestrator_started"] = True

                if "creator output" in content:
                    workflow_markers["creator_called"] = True

                if "critic feedback" in content or "content approved by critic" in content:
                    workflow_markers["critic_called"] = True

                if "calling formatter agent" in content:
                    workflow_markers["formatter_called"] = True

                if "workflow complete" in content or "content creation complete" in content:
                    workflow_markers["workflow_completed"] = True

                    # Check if all agents have participated
                    all_agents_done = all(workflow_markers.values())
                    if all_agents_done:
                        break

        # Assert all agents participated
        assert workflow_markers["orchestrator_started"], "Orchestrator did not start workflow"
        assert workflow_markers["creator_called"], "Creator agent was not called"
        assert workflow_markers["critic_called"], "Critic agent was not called"
        assert workflow_markers["formatter_called"], "Formatter agent was not called"
        assert workflow_markers["workflow_completed"], "Workflow did not complete successfully"

        assert all_agents_done, "Not all agents completed their work before timeout"

        # Verify the final output contains HTML (since we requested HTML format)
        all_messages_text = " ".join([msg.content.content for msg in messages if msg.content])
        assert "<!doctype html>" in all_messages_text.lower() or "<html" in all_messages_text.lower(), (
            "Final output does not contain HTML formatting"
        )


class TestStreamingEvents:
    """Test streaming event sending."""

    @pytest.mark.asyncio
    async def test_multi_agent_workflow_streaming(self, client: AsyncAgentex, agent_id: str):
        """Test the multi-agent workflow with streaming responses and early exit."""
        # Create a task for the orchestrator
        task_response = await client.agents.create_task(agent_id, params=ParamsCreateTaskRequest(name=uuid.uuid1().hex))
        task = task_response.result
        assert task is not None

        # Send a simpler content creation request for faster execution
        request_json = {
            "request": "Write a short greeting",
            "rules": ["Under 20 words", "Friendly"],
            "target_format": "Markdown",
        }

        import json

        print("\n🔄 Streaming multi-agent workflow responses...")

        # Track which agents have completed their work
        workflow_markers = {
            "orchestrator_started": False,
            "creator_called": False,
            "critic_called": False,
            "formatter_called": False,
            "workflow_completed": False,
        }

        # Collect messages from stream and track agent participation
        all_messages = []
        creator_iterations = 0
        critic_feedback_count = 0

        # Send the event to trigger the agent workflow
        event_content = TextContentParam(type="text", author="user", content=json.dumps(request_json))
        await client.agents.send_event(agent_id=agent_id, params={"task_id": task.id, "content": event_content})

        async for event in stream_agent_response(
            client=client,
            task_id=task.id,
            timeout=120,
        ):
            # Handle different event types
            if event.get("type") == "full":
                content = event.get("content", {})
                if content.get("type") == "text" and content.get("author") == "agent":
                    message_text = content.get("content", "")
                    all_messages.append(message_text)

                    # Track agent participation
                    content_lower = message_text.lower()

                    if "starting content workflow" in content_lower:
                        workflow_markers["orchestrator_started"] = True

                    if "creator output" in content_lower:
                        creator_iterations += 1
                        workflow_markers["creator_called"] = True

                    if "critic feedback" in content_lower or "content approved by critic" in content_lower:
                        if "critic feedback" in content_lower:
                            critic_feedback_count += 1
                        workflow_markers["critic_called"] = True

                    if "calling formatter agent" in content_lower:
                        workflow_markers["formatter_called"] = True

                    if "workflow complete" in content_lower or "content creation complete" in content_lower:
                        workflow_markers["workflow_completed"] = True

                        # Check if all agents have participated
                        all_agents_done = all(workflow_markers.values())
                        if all_agents_done:
                            break

        # Validate we got streaming responses
        assert len(all_messages) > 0, "No messages received from streaming"

        # Assert all agents participated
        assert workflow_markers["orchestrator_started"], "Orchestrator did not start workflow"
        assert workflow_markers["creator_called"], "Creator agent was not called"
        assert workflow_markers["critic_called"], "Critic agent was not called"
        assert workflow_markers["formatter_called"], "Formatter agent was not called"
        assert workflow_markers["workflow_completed"], "Workflow did not complete successfully"

        # Verify the final output contains Markdown (since we requested Markdown format)
        combined_response = " ".join(all_messages)
        assert "markdown" in combined_response.lower() or "#" in combined_response, (
            "Final output does not contain Markdown formatting"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
