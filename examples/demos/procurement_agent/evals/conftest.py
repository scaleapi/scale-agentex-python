"""
Pytest fixtures for procurement agent evals.

Provides workflow setup, transcript extraction, and human input simulation.
"""
from __future__ import annotations

import os
import uuid
import asyncio
from typing import Any, AsyncGenerator
from datetime import datetime as dt

import pytest
import pytest_asyncio
from temporalio.client import Client, WorkflowHandle

from agentex.types.task import Task
from agentex.types.agent import Agent
from agentex.lib.types.acp import CreateTaskParams

# Set environment variables for local development
os.environ.setdefault("AGENT_NAME", "procurement-agent")
os.environ.setdefault("ACP_URL", "http://localhost:8000")
os.environ.setdefault("WORKFLOW_NAME", "procurement-agent")
os.environ.setdefault("WORKFLOW_TASK_QUEUE", "procurement_agent_queue")
os.environ.setdefault("TEMPORAL_ADDRESS", "localhost:7233")


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def temporal_client() -> AsyncGenerator[Client, None]:
    """Create a Temporal client for the test session."""
    client = await Client.connect(
        os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
    )
    yield client
    # Client doesn't need explicit close


@pytest_asyncio.fixture
async def workflow_handle(temporal_client: Client) -> AsyncGenerator[WorkflowHandle, None]:
    """
    Start a fresh workflow for each test.

    Creates a unique workflow ID and starts the procurement agent workflow.
    Yields the handle for sending signals and querying state.
    """
    workflow_id = f"eval-{uuid.uuid4()}"
    task_queue = os.environ.get("WORKFLOW_TASK_QUEUE", "procurement_agent_queue")
    workflow_name = os.environ.get("WORKFLOW_NAME", "procurement-agent")

    # Create agent and task params
    now = dt.now()
    agent = Agent(
        id="procurement-agent",
        name="procurement-agent",
        acp_type="agentic",
        description="Procurement agent for construction delivery management",
        created_at=now,
        updated_at=now,
    )
    task = Task(id=workflow_id)
    create_task_params = CreateTaskParams(agent=agent, task=task, params=None)

    # Start the workflow
    handle = await temporal_client.start_workflow(
        workflow_name,
        create_task_params,
        id=workflow_id,
        task_queue=task_queue,
    )

    # Give workflow time to initialize
    await asyncio.sleep(2)

    yield handle

    # Cleanup: terminate the workflow after test
    try:
        await handle.terminate("Test completed")
    except Exception:
        pass  # Workflow may have already completed


async def send_event(handle: WorkflowHandle, event: Any) -> None:
    """
    Send an event to the workflow via signal.

    Args:
        handle: The workflow handle
        event: A Pydantic event model (will be serialized to JSON)
    """
    event_json = event.model_dump_json()
    await handle.signal("send_event", event_json)


async def send_human_response(handle: WorkflowHandle, response: str) -> None:
    """
    Send a human response to the workflow.

    This simulates a user responding in the UI to a wait_for_human escalation.

    Args:
        handle: The workflow handle
        response: The human's text response
    """
    # Import here to avoid circular imports
    from agentex.types.task import Task
    from agentex.types.agent import Agent
    from agentex.types.event import Event
    from agentex.lib.types.acp import SendEventParams
    from agentex.types.text_content import TextContent

    now = dt.now()
    agent = Agent(
        id="procurement-agent",
        name="procurement-agent",
        acp_type="agentic",
        description="Procurement agent for construction delivery management",
        created_at=now,
        updated_at=now,
    )
    task = Task(id=handle.id)
    event = Event(
        id=str(uuid.uuid4()),
        agent_id="procurement-agent",
        task_id=handle.id,
        sequence_id=1,
        content=TextContent(author="user", content=response),
    )
    params = SendEventParams(agent=agent, task=task, event=event)

    await handle.signal("receive_event", params)


async def wait_for_processing(_handle: WorkflowHandle, timeout_seconds: float = 60) -> None:
    """
    Wait for the workflow to finish processing an event.

    Polls the workflow until no more activities are running.

    Args:
        _handle: The workflow handle (unused, reserved for future polling)
        timeout_seconds: Maximum time to wait
    """
    # Simple approach: wait a fixed time for agent to process
    # In production, you'd poll workflow state more intelligently
    await asyncio.sleep(timeout_seconds)


async def get_workflow_transcript(handle: WorkflowHandle) -> list[dict[str, Any]]:
    """
    Extract the conversation transcript from workflow history.

    Queries the workflow to get the internal state containing tool calls.

    Args:
        handle: The workflow handle

    Returns:
        List of message dicts containing tool calls and responses
    """
    # Query workflow state to get the input_list (conversation history)
    # This requires the workflow to expose a query handler

    # For now, we'll extract from workflow history events
    # The tool calls appear in activity completions
    transcript = []

    async for event in handle.fetch_history_events():
        # Look for activity completed events
        if hasattr(event, 'activity_task_completed_event_attributes'):
            attrs = event.activity_task_completed_event_attributes
            if attrs and hasattr(attrs, 'result'):
                # Activity results contain tool execution info
                transcript.append({
                    "type": "activity_completed",
                    "result": str(attrs.result) if attrs.result else None,
                })

        # Look for activity scheduled events (contains tool name)
        if hasattr(event, 'activity_task_scheduled_event_attributes'):
            attrs = event.activity_task_scheduled_event_attributes
            if attrs and hasattr(attrs, 'activity_type'):
                activity_name = attrs.activity_type.name if attrs.activity_type else None
                transcript.append({
                    "type": "function_call",
                    "name": activity_name,
                })

    return transcript


async def get_transcript_event_count(handle: WorkflowHandle) -> int:
    """Get the current number of events in the transcript."""
    transcript = await get_workflow_transcript(handle)
    return len(transcript)


def get_new_tool_calls(
    full_transcript: list[dict[str, Any]],
    previous_count: int
) -> list[dict[str, Any]]:
    """
    Get only the new tool calls since the previous checkpoint.

    Args:
        full_transcript: The complete transcript from get_workflow_transcript
        previous_count: The transcript length before the event was sent

    Returns:
        List of new tool call entries
    """
    return full_transcript[previous_count:]


def get_workflow_id(handle: WorkflowHandle) -> str:
    """Get the workflow ID from a handle."""
    return handle.id
