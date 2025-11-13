"""
Tests for at010-agent-chat (temporal agent)

Prerequisites:
    - AgentEx services running (make dev)
    - Temporal server running
    - Agent running: agentex agents run --manifest manifest.yaml

Key differences from base async (040_other_sdks):
1. Temporal Integration: Uses Temporal workflows for durable execution
2. State Management: State is managed within the workflow instance
3. No Race Conditions: Temporal ensures sequential event processing
4. Durable Execution: Workflow state survives restarts

Run: pytest tests/test_agent.py -v
"""

import pytest

from agentex.lib.testing import async_test_agent, assert_valid_agent_response

AGENT_NAME = "at010-agent-chat"


@pytest.mark.asyncio
async def test_agent_basic():
    """Test basic agent functionality."""
    async with async_test_agent(agent_name=AGENT_NAME) as test:
        response = await test.send_event("Test message", timeout_seconds=60.0)
        assert_valid_agent_response(response)


@pytest.mark.asyncio
async def test_agent_streaming():
    """Test streaming responses."""
    async with async_test_agent(agent_name=AGENT_NAME) as test:
        events = []
        async for event in test.send_event_and_stream("Stream test", timeout_seconds=60.0):
            events.append(event)
            if event.get("type") == "done":
                break
        assert len(events) > 0

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
        """Test multiple turns of conversation with state preservation."""
        # Create a task for this conversation
        task_response = await client.agents.create_task(agent_id, params=ParamsCreateTaskRequest(name=uuid.uuid1().hex))
        task = task_response.result
        assert task is not None

        # Wait for workflow to initialize
        await asyncio.sleep(1)

        # First turn
        user_message_1 = "My favorite color is blue."
        async for message in send_event_and_poll_yielding(
            client=client,
            agent_id=agent_id,
            task_id=task.id,
            user_message=user_message_1,
            timeout=20,
            sleep_interval=1.0,
        ):
            assert isinstance(message, TaskMessage)
            if (
                message.content
                and message.content.type == "text"
                and message.content.author == "agent"
                and message.content.content
            ):
                break

        # Wait a bit for state to update
        await asyncio.sleep(2)

        # Second turn - reference previous context
        found_response = False
        user_message_2 = "What did I just tell you my favorite color was?"
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
                assert "blue" in response_text, f"Expected 'blue' in response but got: {response_text}"
                found_response = True
                break

        assert found_response, "Did not receive final agent text response with context recall"


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

        async def stream_messages() -> None:  # noqa: ANN101
            nonlocal user_message_found, agent_response_found
            async for event in stream_agent_response(
                client=client,
                task_id=task.id,
                timeout=60,
            ):
                msg_type = event.get("type")
                if msg_type == "full":
                    task_message_update = StreamTaskMessageFull.model_validate(event)
                    if task_message_update.parent_task_message and task_message_update.parent_task_message.id:
                        finished_message = await client.messages.retrieve(task_message_update.parent_task_message.id)
                        if (
                            finished_message.content
                            and finished_message.content.type == "text"
                            and finished_message.content.author == "user"
                        ):
                            user_message_found = True
                        elif (
                            finished_message.content
                            and finished_message.content.type == "text"
                            and finished_message.content.author == "agent"
                        ):
                            agent_response_found = True
                        elif finished_message.content and finished_message.content.type == "reasoning":
                            tool_response_found = True
                elif msg_type == "done":
                    task_message_update = StreamTaskMessageDone.model_validate(event)
                    if task_message_update.parent_task_message and task_message_update.parent_task_message.id:
                        finished_message = await client.messages.retrieve(task_message_update.parent_task_message.id)
                        if finished_message.content and finished_message.content.type == "reasoning":
                            agent_response_found = True
                    continue

        stream_task = asyncio.create_task(stream_messages())

        event_content = TextContentParam(type="text", author="user", content=user_message)
        await client.agents.send_event(agent_id=agent_id, params={"task_id": task.id, "content": event_content})

        # Wait for streaming to complete
        await stream_task

        assert user_message_found, "User message not found in stream"
        assert agent_response_found, "Agent response not found in stream"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
