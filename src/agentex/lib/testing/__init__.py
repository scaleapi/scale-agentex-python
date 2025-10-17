"""
AgentEx Testing Framework

Provides testing utilities for AgentEx agents with real infrastructure testing.

Quick Start:
    ```python
    import pytest
    from agentex.lib.testing import test_sync_agent, test_agentic_agent


    # Sync agents - immediate response
    def test_sync_simple():
        with test_sync_agent() as test:
            response = test.send_message("Hello!")
            assert response is not None


    # Agentic agents - async event-driven
    @pytest.mark.asyncio
    async def test_agentic_simple():
        async with test_agentic_agent() as test:
            response = await test.send_event("Hello!", timeout_seconds=15.0)
            assert response is not None
    ```

Key Principle: Different agent types use appropriate client methods.
- Sync agents: Use send_message() for immediate responses
- Agentic/Temporal agents: Use send_event() with polling for async responses

Components exported:
- test_sync_agent(), test_agentic_agent() - Simple context managers
- Fixtures: real_agentex_client, real_agentex_async_client, sync_agent, agentic_agent
- Assertions: assert_agent_response_contains(), assert_conversation_maintains_context()
"""

from agentex.lib.testing.fixtures import (
    sync_agent,
    agentic_agent,
    real_agentex_client,
    real_agentex_async_client,
)
from agentex.lib.testing.sessions import (
    SyncAgentTest,
    AgenticAgentTest,
    test_sync_agent,
    test_agentic_agent,
    sync_agent_test_session,
    agentic_agent_test_session,
)
from agentex.lib.testing.assertions import (
    extract_response_text,
    assert_valid_agent_response,
    assert_agent_response_contains,
    assert_conversation_maintains_context,
)

__all__ = [
    # Simple testing functions (recommended)
    "test_sync_agent",
    "test_agentic_agent",
    # Client fixtures
    "real_agentex_client",
    "real_agentex_async_client",
    # Agent fixtures
    "sync_agent",
    "agentic_agent",
    # Test session classes
    "SyncAgentTest",
    "AgenticAgentTest",
    # Session managers
    "sync_agent_test_session",
    "agentic_agent_test_session",
    # Assertions
    "assert_agent_response_contains",
    "assert_valid_agent_response",
    "assert_conversation_maintains_context",
    "extract_response_text",
]
