"""
Tutorial 20.1: Agentic Agent Testing

This tutorial demonstrates how to test agentic agents that use event-driven architecture.

Prerequisites:
    - AgentEx services running (make dev)
    - An agentic agent running (e.g., tutorial 10_agentic)

Run:
    pytest test_agentic_agent.py -v
"""

import pytest

from agentex.lib.testing import assert_valid_agent_response, test_agentic_agent


@pytest.mark.asyncio
async def test_agentic_agent_responds():
    """Test that agentic agent responds to events."""
    async with test_agentic_agent() as test:
        # Send event and wait for response
        response = await test.send_event("Hello! How are you?", timeout_seconds=15.0)

        # Verify we got a valid response
        assert_valid_agent_response(response)
        print(f"✓ Agent responded: {response.content[:50]}...")


@pytest.mark.asyncio
async def test_agentic_agent_multi_turn():
    """Test that agentic agent handles multi-turn conversation."""
    async with test_agentic_agent() as test:
        # First exchange
        response1 = await test.send_event("Hello!", timeout_seconds=15.0)
        assert_valid_agent_response(response1)
        print("✓ First exchange complete")

        # Second exchange
        response2 = await test.send_event("Can you help me with a task?", timeout_seconds=15.0)
        assert_valid_agent_response(response2)
        print("✓ Second exchange complete")

        # Verify conversation history
        history = await test.get_conversation_history()
        assert len(history) >= 2  # User messages tracked
        print(f"✓ Conversation history: {len(history)} messages")


@pytest.mark.asyncio
async def test_agentic_agent_context():
    """Test that agentic agent maintains conversation context."""
    async with test_agentic_agent() as test:
        # Establish context
        response1 = await test.send_event("My name is Jordan and I work in finance", timeout_seconds=15.0)
        assert_valid_agent_response(response1)
        print("✓ Context established")

        # Query the context
        response2 = await test.send_event("What field do I work in?", timeout_seconds=15.0)
        assert_valid_agent_response(response2)
        print(f"✓ Agent responded to context query: {response2.content[:50]}...")


@pytest.mark.asyncio
async def test_agentic_agent_timeout_handling():
    """Test proper timeout configuration for different scenarios."""
    async with test_agentic_agent() as test:
        # Quick question - short timeout
        response = await test.send_event("Hi!", timeout_seconds=10.0)
        assert_valid_agent_response(response)
        print("✓ Short timeout worked")


@pytest.mark.asyncio
async def test_agentic_agent_conversation_flow():
    """Test natural conversation flow with agentic agent."""
    async with test_agentic_agent() as test:
        # Simulate a natural conversation
        messages = [
            "I need help with a Python project",
            "It's about data processing",
            "What should I start with?",
        ]

        responses = []
        for i, msg in enumerate(messages):
            response = await test.send_event(msg, timeout_seconds=20.0)
            assert_valid_agent_response(response)
            responses.append(response)
            print(f"✓ Exchange {i+1}/3 complete")

        # All exchanges should succeed
        assert len(responses) == 3
        print("✓ Complete conversation flow successful")


if __name__ == "__main__":
    print("Run with: pytest test_agentic_agent.py -v")
