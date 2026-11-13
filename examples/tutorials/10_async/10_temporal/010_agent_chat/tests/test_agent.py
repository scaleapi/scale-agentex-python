"""
Sample tests for AgentEx Temporal agent with OpenAI Agents SDK integration.

This test suite demonstrates how to test agents that integrate:
- OpenAI Agents SDK with streaming (via Temporal workflows)
- MCP (Model Context Protocol) servers for tool access
- Multi-turn conversations with state management
- Tool usage (calculator and web search via MCP)

Key differences from base async (040_other_sdks):
1. Temporal Integration: Uses Temporal workflows for durable execution
2. State Management: State is managed within the workflow instance
3. No Race Conditions: Temporal ensures sequential event processing
4. Durable Execution: Workflow state survives restarts

To run these tests:
1. Make sure the agent is running (via docker-compose or `agentex agents run`)
2. Set the AGENTEX_API_BASE_URL environment variable if not using default
3. Ensure OPENAI_API_KEY is set in the environment
4. Run: pytest test_agent.py -v

The workflow's signal handler is also unit-tested offline (TestOfflineSignalHandler);
those tests need no running agent, Temporal, network or API key.

Configuration:
- AGENTEX_API_BASE_URL: Base URL for the AgentEx server (default: http://localhost:5003)
- AGENT_NAME: Name of the agent to test (default: at010-agent-chat)
"""

import os
import uuid
import asyncio
from types import SimpleNamespace
from typing import Any
from datetime import datetime, timezone
from contextlib import contextmanager
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from test_utils.async_utils import (
    stream_agent_response,
    send_event_and_poll_yielding,
)

from agentex import AsyncAgentex
from agentex.types import TaskMessage, TextContent
from agentex.types.task import Task
from agentex.types.agent import Agent
from agentex.types.event import Event
from agentex.protocol.acp import SendEventParams
from agentex.types.data_content import DataContent
from agentex.types.agent_rpc_params import ParamsCreateTaskRequest
from agentex.types.agent_rpc_result import StreamTaskMessageDone, StreamTaskMessageFull
from agentex.types.reasoning_content import ReasoningContent
from agentex.types.text_content_param import TextContentParam
from agentex.types.tool_request_content import ToolRequestContent
from agentex.types.tool_response_content import ToolResponseContent

# Configuration from environment variables
AGENTEX_API_BASE_URL = os.environ.get("AGENTEX_API_BASE_URL", "http://localhost:5003")
AGENT_NAME = os.environ.get("AGENT_NAME", "at010-agent-chat")


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
    """Test non-streaming event sending and polling with OpenAI Agents SDK."""

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
        user_message = "Hello! Please introduce yourself briefly."
        messages = []
        user_message_found = False
        async for message in send_event_and_poll_yielding(
            client=client,
            agent_id=agent_id,
            task_id=task.id,
            user_message=user_message,
            timeout=30,
            sleep_interval=1.0,
        ):
            assert isinstance(message, TaskMessage)
            messages.append(message)

            if message.content and message.content.author == "user":
                assert message.content == TextContent(
                    author="user",
                    content=user_message,
                    type="text",
                )
                user_message_found = True
                break

        assert user_message_found, "User message not found"

    @pytest.mark.asyncio
    async def test_send_event_and_poll_with_calculator(self, client: AsyncAgentex, agent_id: str):
        """Test sending an event that triggers calculator tool usage and polling for the response."""
        # Create a task for this conversation
        task_response = await client.agents.create_task(agent_id, params=ParamsCreateTaskRequest(name=uuid.uuid1().hex))
        task = task_response.result
        assert task is not None

        # Wait for workflow to initialize
        await asyncio.sleep(1)

        # Send a message that could trigger the calculator tool (though with reasoning, it may not need it)
        user_message = "What is 15 multiplied by 37?"
        has_final_agent_response = False
        async for message in send_event_and_poll_yielding(
            client=client,
            agent_id=agent_id,
            task_id=task.id,
            user_message=user_message,
            timeout=60,  # Longer timeout for tool use
            sleep_interval=1.0,
        ):
            assert isinstance(message, TaskMessage)
            if message.content and message.content.type == "text" and message.content.author == "agent":
                # Check that the answer contains 555 (15 * 37)
                if "555" in message.content.content:
                    has_final_agent_response = True
                    break

        assert has_final_agent_response, "Did not receive final agent text response with correct answer"

    @pytest.mark.asyncio
    async def test_multi_turn_conversation(self, client: AsyncAgentex, agent_id: str):
        """
        Test message ordering by sending messages about distinct topics.

        This validates that the agent receives messages in chronological order.
        If messages are reversed (newest first), the agent would respond about
        the wrong topic.
        """
        # Create a task for this conversation
        task_response = await client.agents.create_task(agent_id, params=ParamsCreateTaskRequest(name=uuid.uuid1().hex))
        task = task_response.result
        assert task is not None

        # Wait for workflow to initialize
        await asyncio.sleep(1)

        # First turn - ask about tennis
        user_message_1 = "Tell me about tennis. You must include the word 'tennis' in your response."
        first_turn_found = False
        async for message in send_event_and_poll_yielding(
            client=client,
            agent_id=agent_id,
            task_id=task.id,
            user_message=user_message_1,
            timeout=30,
            sleep_interval=1.0,
        ):
            assert isinstance(message, TaskMessage)
            if (
                message.content
                and message.content.type == "text"
                and message.content.author == "agent"
                and message.content.content
            ):
                # Validate response is about tennis
                assert "tennis" in message.content.content.lower(), "First response should be about tennis"
                first_turn_found = True
                break

        assert first_turn_found, "First turn response not found"

        # Wait a bit for state to update
        await asyncio.sleep(2)

        # Second turn - ask about basketball (different topic)
        # If message ordering is wrong, agent might respond about tennis instead
        found_response = False
        user_message_2 = "Now tell me about basketball. You must include the word 'basketball' in your response. Do not mention tennis."
        async for message in send_event_and_poll_yielding(
            client=client,
            agent_id=agent_id,
            task_id=task.id,
            user_message=user_message_2,
            timeout=30,
            sleep_interval=1.0,
        ):
            if (
                message.content
                and message.content.type == "text"
                and message.content.author == "agent"
                and message.content.content
            ):
                response_text = message.content.content.lower()
                # Validate response is about basketball, not tennis
                assert "basketball" in response_text, f"Second response should be about basketball, got: {response_text}"
                found_response = True
                break

        assert found_response, "Did not receive final agent text response with correct topic"


class TestStreamingEvents:
    """Test streaming event sending with OpenAI Agents SDK and tool usage."""

    @pytest.mark.asyncio
    async def test_send_event_and_stream_with_reasoning(self, client: AsyncAgentex, agent_id: str):
        """Test streaming a simple response without tool usage."""
        # Create a task for this conversation
        task_response = await client.agents.create_task(agent_id, params=ParamsCreateTaskRequest(name=uuid.uuid1().hex))
        task = task_response.result
        assert task is not None

        # Wait for workflow to initialize
        await asyncio.sleep(1)

        user_message = "Tell me a very short joke about programming."

        # Check for user message and agent response
        user_message_found = False
        agent_response_found = False
        reasoning_found = False
        async def stream_messages() -> None:
            nonlocal user_message_found, agent_response_found, reasoning_found
            async for event in stream_agent_response(
                client=client,
                task_id=task.id,
                timeout=90,  # Increased timeout for CI environments
            ):
                # A turn emits several messages (user echo, reasoning, agent text),
                # each ending in "full" or "done"; consume until the text reply lands.
                msg_type = event.get("type")
                if msg_type == "full":
                    parent_task_message = StreamTaskMessageFull.model_validate(event).parent_task_message
                elif msg_type == "done":
                    parent_task_message = StreamTaskMessageDone.model_validate(event).parent_task_message
                else:
                    continue

                if parent_task_message and parent_task_message.id:
                    finished_message = await client.messages.retrieve(parent_task_message.id)
                    content = finished_message.content
                    if content and content.type == "text" and content.author == "user":
                        user_message_found = True
                    elif content and content.type == "text" and content.author == "agent":
                        agent_response_found = True
                    elif content and content.type == "reasoning":
                        reasoning_found = True

                # Stop once both the user echo and the agent's text reply are seen.
                if user_message_found and agent_response_found:
                    break

        stream_task = asyncio.create_task(stream_messages())
        event_content = TextContentParam(type="text", author="user", content=user_message)
        await client.agents.send_event(agent_id=agent_id, params={"task_id": task.id, "content": event_content})
        await stream_task

        assert user_message_found, "User message not found in stream"
        assert agent_response_found, "Agent response not found in stream"


# ---------------------------------------------------------------------------
# Offline signal-handler tests (no running agent, Temporal, network or API key)
# ---------------------------------------------------------------------------

TASK_ID = "task-offline-1"
USER_TEXT = TextContent(author="user", content="What is 2 + 2?")


def _send_event_params(content: Any) -> SendEventParams:
    """Real ``SendEventParams``, as the ACP delivers an ``event/send`` to the workflow signal."""
    now = datetime.now(timezone.utc)
    return SendEventParams(
        agent=Agent(id="agent-1", acp_type="async", name=AGENT_NAME, description="", created_at=now, updated_at=now),
        task=Task(id=TASK_ID),
        event=Event(id="event-1", agent_id="agent-1", task_id=TASK_ID, sequence_id=1, content=content),
    )


# Event content a caller can send that this handler must not process: Event.content is
# optional, only TextContent carries text, and the agent only answers user messages.
IGNORED_CONTENTS = [
    pytest.param(None, id="no-content"),
    pytest.param(DataContent(author="user", data={}), id="data"),
    pytest.param(ReasoningContent(author="user", summary=["thinking"], type="reasoning"), id="reasoning"),
    pytest.param(
        ToolRequestContent(author="user", name="calculator", tool_call_id="call-1", arguments={"a": 1}),
        id="tool-request",
    ),
    pytest.param(
        ToolResponseContent(author="user", name="calculator", tool_call_id="call-1", content={"k": "v"}),
        id="tool-response-dict",
    ),
    pytest.param(
        ToolResponseContent(author="user", name="calculator", tool_call_id="call-1", content=[1, 2]),
        id="tool-response-list",
    ),
    pytest.param(TextContent(author="agent", content="I am not the user"), id="agent-text"),
]


class _FakeSpan:
    id = "span-offline-1"
    output: Any = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False


@contextmanager
def _mock_adk():
    """Mock the ``adk`` calls the handler makes, so nothing leaves the process."""
    run_result = SimpleNamespace(
        final_input_list=[
            {"role": "user", "content": USER_TEXT.content},
            {"role": "assistant", "content": "4"},
        ]
    )
    with patch("project.workflow.adk.messages.create", new=AsyncMock()) as create, patch(
        "project.workflow.adk.tracing.span", return_value=_FakeSpan()
    ) as span, patch(
        "project.workflow.adk.providers.openai.run_agent_streamed_auto_send",
        new=AsyncMock(return_value=run_result),
    ) as run_agent:
        yield create, span, run_agent


class TestOfflineSignalHandler:
    """Unit tests for ``on_task_event_send``, called directly with real ``SendEventParams``."""

    @staticmethod
    def _workflow():
        from project.workflow import StateModel, At010AgentChatWorkflow

        # Build the instance without Temporal: skip __init__ and set what it would set,
        # plus the state on_task_create initialises.
        wf = At010AgentChatWorkflow.__new__(At010AgentChatWorkflow)
        wf.display_name = AGENT_NAME
        wf._complete_task = False
        wf._state = StateModel(input_list=[], turn_number=0)
        return wf

    @pytest.mark.asyncio
    @pytest.mark.parametrize("content", IGNORED_CONTENTS)
    async def test_unprocessable_event_is_ignored(self, content):
        """Return without raising (that would wedge the task) and without side effects."""
        with _mock_adk() as (create, span, run_agent):
            wf = self._workflow()
            await wf.on_task_event_send(_send_event_params(content))

        create.assert_not_awaited()
        span.assert_not_called()
        run_agent.assert_not_awaited()
        assert wf._state.turn_number == 0
        assert wf._state.input_list == []

    @pytest.mark.asyncio
    async def test_user_text_event_runs_a_turn(self):
        """A user text event is echoed, added to the history and answered by the agent."""
        with _mock_adk() as (create, span, run_agent):
            wf = self._workflow()
            await wf.on_task_event_send(_send_event_params(USER_TEXT))

        assert wf._state.turn_number == 1
        span.assert_called_once()
        # The first message is the echo of the user's own message.
        assert create.await_args_list[0].kwargs["content"] == USER_TEXT
        run_agent.assert_awaited_once()
        assert run_agent.await_args.kwargs["input_list"] == [{"role": "user", "content": USER_TEXT.content}]
        assert wf._state.input_list == run_agent.return_value.final_input_list

    @pytest.mark.asyncio
    async def test_event_before_state_is_initialised_waits_for_it(self):
        """An event handled before on_task_create has run waits for the state, not raises."""
        from project.workflow import StateModel

        wf = self._workflow()
        wf._state = None

        async def _wait_condition(condition):
            assert not condition()
            wf._state = StateModel(input_list=[], turn_number=0)  # on_task_create runs
            assert condition()

        with _mock_adk() as (create, _span, _run_agent), patch(
            "project.workflow.workflow.wait_condition", new=AsyncMock(side_effect=_wait_condition)
        ) as wait_condition:
            await wf.on_task_event_send(_send_event_params(USER_TEXT))

        wait_condition.assert_awaited_once()
        assert wf._state.turn_number == 1
        assert create.await_args_list[0].kwargs["content"] == USER_TEXT


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
