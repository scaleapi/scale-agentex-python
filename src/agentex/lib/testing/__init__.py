"""
AgentEx Testing Framework

Simplified API for testing agents with real AgentEx infrastructure.

Quick Start:
    ```python
    import pytest
    from agentex.lib.testing import test_sync_agent, test_agentic_agent


    # Sync agents - MUST specify which agent
    def test_my_sync_agent():
        with test_sync_agent(agent_name="my-agent") as test:
            response = test.send_message("Hello!")
            assert response is not None


    # Agentic agents
    @pytest.mark.asyncio
    async def test_my_agentic_agent():
        async with test_agentic_agent(agent_name="my-agent") as test:
            response = await test.send_event("Hello!", timeout_seconds=15.0)
            assert response is not None
    ```

Core Principles:
- **Explicit agent selection required** (no auto-selection)
- Use send_message() for sync agents (immediate response)
- Use send_event() for agentic agents (async polling)

To discover agent names:
    Run: agentex agents list

Documentation:
    See USAGE.md in this directory for complete guide with examples
"""

from agentex.lib.testing.sessions import (
    test_sync_agent,
    test_agentic_agent,
)
from agentex.lib.testing.streaming import (
    stream_task_messages,
    stream_agent_response,
    collect_streaming_deltas,
)
from agentex.lib.testing.assertions import (
    assert_valid_agent_response,
    assert_agent_response_contains,
    assert_conversation_maintains_context,
)
from agentex.lib.testing.exceptions import (
    AgentTimeoutError,
    AgentNotFoundError,
    AgentSelectionError,
)

__all__ = [
    # Core testing API
    "test_sync_agent",
    "test_agentic_agent",
    # Assertions
    "assert_valid_agent_response",
    "assert_agent_response_contains",
    "assert_conversation_maintains_context",
    # Streaming utilities
    "stream_agent_response",
    "stream_task_messages",
    "collect_streaming_deltas",
    # Common exceptions users might catch
    "AgentNotFoundError",
    "AgentSelectionError",
    "AgentTimeoutError",
]
