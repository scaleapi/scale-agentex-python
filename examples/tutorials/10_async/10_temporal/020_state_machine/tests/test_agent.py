"""
Sample tests for AgentEx Temporal State Machine agent.

This test suite demonstrates how to test a state machine-based agent that:
- Uses state transitions (WAITING → CLARIFYING → PERFORMING_DEEP_RESEARCH)
- Asks follow-up questions before performing research
- Performs deep web research using MCP servers
- Handles multi-turn conversations with context preservation

Key features tested:
1. State Machine Flow: Agent transitions through multiple states
2. Follow-up Questions: Agent clarifies queries before research
3. Deep Research: Agent performs extensive web research
4. Multi-turn Support: User can ask follow-ups about research

To run these tests:
1. Make sure the agent is running (via docker-compose or `agentex agents run`)
2. Set the AGENTEX_API_BASE_URL environment variable if not using default
3. Ensure OPENAI_API_KEY is set in the environment
4. Run: pytest test_agent.py -v

The workflow's signal handler is also unit-tested offline (TestOfflineSignalHandler);
those tests need no running agent, Temporal, network or API key.

Configuration:
- AGENTEX_API_BASE_URL: Base URL for the AgentEx server (default: http://localhost:5003)
- AGENT_NAME: Name of the agent to test (default: at020-state-machine)
"""

import os
import uuid
import asyncio
from typing import Any
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from test_utils.async_utils import (
    stream_task_messages,
    send_event_and_poll_yielding,
)

from agentex import AsyncAgentex
from agentex.types.span import Span
from agentex.types.task import Task
from agentex.types.agent import Agent
from agentex.types.event import Event
from agentex.protocol.acp import SendEventParams
from agentex.types.data_content import DataContent
from agentex.types.text_content import TextContent
from agentex.types.agent_rpc_params import ParamsCreateTaskRequest
from agentex.types.reasoning_content import ReasoningContent
from agentex.types.text_content_param import TextContentParam
from agentex.types.tool_request_content import ToolRequestContent
from agentex.types.tool_response_content import ToolResponseContent

# Configuration from environment variables
AGENTEX_API_BASE_URL = os.environ.get("AGENTEX_API_BASE_URL", "http://localhost:5003")
AGENT_NAME = os.environ.get("AGENT_NAME", "at020-state-machine")


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
    """Test non-streaming event sending and polling with state machine workflow."""
    @pytest.mark.asyncio
    async def test_send_event_and_poll_simple_query(self, client: AsyncAgentex, agent_id: str):
        """Test sending a simple event and polling for the response (no tool use)."""
        # Create a task for this conversation
        task_response = await client.agents.create_task(agent_id, params=ParamsCreateTaskRequest(name=uuid.uuid1().hex))
        task = task_response.result
        assert task is not None

        # Wait for workflow to initialize
        await asyncio.sleep(1)

        # Send a simple message that shouldn't require tool use
        user_message = "Hello! Please tell me the latest news about AI and AI startups."
        messages = []
        found_agent_message = False
        async for message in send_event_and_poll_yielding(
            client=client,
            agent_id=agent_id,
            task_id=task.id,
            user_message=user_message,
            timeout=30,
            sleep_interval=1.0,
        ):
            messages.append(message)
            ## we should expect to get a question from the agent
            if message.content.type == "text" and message.content.author == "agent":
                found_agent_message = True
                break

        assert found_agent_message, "Did not find an agent message"

        # now we want to clarity that message
        await asyncio.sleep(2)
        next_user_message = "I want to know what viral news came up and which startups failed, got acquired, or became very successful or popular in the last 3 months"
        starting_deep_research_message = False
        uses_tool_requests = False
        async for message in send_event_and_poll_yielding(
            client=client,
            agent_id=agent_id,
            task_id=task.id,
            user_message=next_user_message,
            timeout=30,
            sleep_interval=1.0,
        ):
            if message.content.type == "text" and message.content.author == "agent":
                if "starting deep research" in message.content.content.lower():
                    starting_deep_research_message = True
            if isinstance(message.content, ToolRequestContent):
                uses_tool_requests = True
                break

        assert starting_deep_research_message, "Did not start deep research"
        assert uses_tool_requests, "Did not use tool requests"

class TestStreamingEvents:
    """Test streaming event sending with state machine workflow."""
    @pytest.mark.asyncio
    async def test_send_event_and_stream(self, client: AsyncAgentex, agent_id: str):
        """Test sending an event and streaming the response."""
        # Create a task for this conversation
        task_response = await client.agents.create_task(agent_id, params=ParamsCreateTaskRequest(name=uuid.uuid1().hex))
        task = task_response.result
        assert task is not None

        found_agent_message = False
        user_message = "Hello! Please tell me the latest news about AI and AI startups."
        async def stream_first_turn() -> None:
            nonlocal found_agent_message
            async for message in stream_task_messages(
                client=client,
                task_id=task.id,
                timeout=30,
            ):
                if message.content.type == "text" and message.content.author == "agent":
                    found_agent_message = True
                    break

        stream_task = asyncio.create_task(stream_first_turn())
        await client.agents.send_event(
            agent_id=agent_id,
            params={"task_id": task.id, "content": TextContentParam(type="text", author="user", content=user_message)},
        )
        await stream_task
        assert found_agent_message, "Did not find an agent message"

        await asyncio.sleep(2)
        starting_deep_research_message = False
        uses_tool_requests = False
        next_user_message = "I want to know what viral news came up and which startups failed, got acquired, or became very successful or popular in the last 3 months"
        async def stream_second_turn() -> None:
            nonlocal starting_deep_research_message, uses_tool_requests
            async for message in stream_task_messages(
                client=client,
                task_id=task.id,
                timeout=30,
            ):
                # can you add the same checks as we did in the non-streaming events test?
                if message.content.type == "text" and message.content.author == "agent":
                    if "starting deep research" in message.content.content.lower():
                        starting_deep_research_message = True
                if isinstance(message.content, ToolRequestContent):
                    uses_tool_requests = True
                    break

        stream_task = asyncio.create_task(stream_second_turn())
        await client.agents.send_event(
            agent_id=agent_id,
            params={
                "task_id": task.id,
                "content": TextContentParam(type="text", author="user", content=next_user_message),
            },
        )
        await stream_task

        assert starting_deep_research_message, "Did not start deep research"
        assert uses_tool_requests, "Did not use tool requests"


# ---------------------------------------------------------------------------
# Offline signal-handler tests (no running agent, Temporal, network or API key)
# ---------------------------------------------------------------------------

TASK_ID = "task-offline-1"
USER_TEXT = TextContent(author="user", content="Research the history of solid-state batteries")


def _send_event_params(content: Any) -> SendEventParams:
    """Real ``SendEventParams``, as the ACP delivers an ``event/send`` to the workflow signal."""
    now = datetime.now(timezone.utc)
    return SendEventParams(
        agent=Agent(id="agent-1", acp_type="async", name=AGENT_NAME, description="", created_at=now, updated_at=now),
        task=Task(id=TASK_ID),
        event=Event(id="event-1", agent_id="agent-1", task_id=TASK_ID, sequence_id=1, content=content),
    )


# Event content a caller can send that this handler must not process: Event.content is
# optional, and only TextContent carries the text the research is about.
IGNORED_CONTENTS = [
    pytest.param(None, id="no-content"),
    pytest.param(DataContent(author="user", data={}), id="data"),
    pytest.param(ReasoningContent(author="user", summary=["thinking"], type="reasoning"), id="reasoning"),
    pytest.param(
        ToolRequestContent(author="user", name="web_search", tool_call_id="call-1", arguments={"query": "x"}),
        id="tool-request",
    ),
    pytest.param(
        ToolResponseContent(author="user", name="web_search", tool_call_id="call-1", content={"k": "v"}),
        id="tool-response-dict",
    ),
    pytest.param(
        ToolResponseContent(author="user", name="web_search", tool_call_id="call-1", content=[1, 2]),
        id="tool-response-list",
    ),
]


class TestOfflineSignalHandler:
    """Unit tests for ``on_task_event_send``, called directly with real ``SendEventParams``."""

    @staticmethod
    def _workflow():
        from project.workflow import At020StateMachineWorkflow
        from project.state_machines.deep_research import DeepResearchData, DeepResearchState, DeepResearchStateMachine
        from project.workflows.deep_research.clarify_user_query import ClarifyUserQueryWorkflow
        from project.workflows.deep_research.waiting_for_user_input import WaitingForUserInputWorkflow
        from project.workflows.deep_research.performing_deep_research import PerformingDeepResearchWorkflow

        from agentex.lib.sdk.state_machine.state import State

        # Build the instance without Temporal: skip __init__ and set what it would set.
        wf = At020StateMachineWorkflow.__new__(At020StateMachineWorkflow)
        wf.display_name = AGENT_NAME
        wf.state_machine = DeepResearchStateMachine(
            initial_state=DeepResearchState.WAITING_FOR_USER_INPUT,
            states=[
                State(name=DeepResearchState.CLARIFYING_USER_QUERY, workflow=ClarifyUserQueryWorkflow()),
                State(name=DeepResearchState.WAITING_FOR_USER_INPUT, workflow=WaitingForUserInputWorkflow()),
                State(name=DeepResearchState.PERFORMING_DEEP_RESEARCH, workflow=PerformingDeepResearchWorkflow()),
            ],
            state_machine_data=DeepResearchData(),
            trace_transitions=True,
        )
        return wf

    @pytest.mark.asyncio
    @pytest.mark.parametrize("content", IGNORED_CONTENTS)
    async def test_unprocessable_event_is_ignored(self, content):
        """Return without raising (that would wedge the task) and without side effects."""
        from project.state_machines.deep_research import DeepResearchData, DeepResearchState

        with patch("project.workflow.adk.messages.create", new=AsyncMock()) as create, patch(
            "project.workflow.adk.tracing.start_span", new=AsyncMock()
        ) as start_span:
            wf = self._workflow()
            await wf.on_task_event_send(_send_event_params(content))

        create.assert_not_awaited()
        start_span.assert_not_awaited()
        assert wf.state_machine.get_current_state() == DeepResearchState.WAITING_FOR_USER_INPUT
        assert wf.state_machine.get_state_machine_data() == DeepResearchData()

    @pytest.mark.asyncio
    async def test_user_text_event_starts_clarifying_the_query(self):
        """The first user message becomes the research query and moves the state machine on."""
        from project.state_machines.deep_research import DeepResearchState

        span = Span(id="span-offline-1", name="Turn 2", start_time=datetime.now(timezone.utc), trace_id=TASK_ID)
        with patch("project.workflow.adk.messages.create", new=AsyncMock()) as create, patch(
            "project.workflow.adk.tracing.start_span", new=AsyncMock(return_value=span)
        ) as start_span:
            wf = self._workflow()
            await wf.on_task_event_send(_send_event_params(USER_TEXT))

        data = wf.state_machine.get_state_machine_data()
        assert data is not None
        assert data.user_query == USER_TEXT.content
        assert data.current_turn == 2
        start_span.assert_awaited_once()
        assert start_span.await_args.kwargs["input"] == {"task_id": TASK_ID, "message": USER_TEXT.content}
        assert data.current_span is span
        assert wf.state_machine.get_current_state() == DeepResearchState.CLARIFYING_USER_QUERY
        # The user's message is echoed back under the turn's span.
        create.assert_awaited_once()
        assert create.await_args.kwargs["content"] == TextContent(author="user", content=USER_TEXT.content)
        assert create.await_args.kwargs["parent_span_id"] == span.id


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
