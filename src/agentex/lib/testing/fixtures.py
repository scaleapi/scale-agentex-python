"""
Pytest fixtures for AgentEx behavior testing.

These fixtures provide access to real AgentEx infrastructure for testing.

Environment Variables:
    AGENTEX_BASE_URL: AgentEx server URL (default: http://localhost:5003)
    AGENTEX_TIMEOUT: Health check timeout in seconds (default: 2.0)
"""

import os

import pytest
import pytest_asyncio

from agentex import Agentex, AsyncAgentex

# Configuration
AGENTEX_BASE_URL = os.getenv("AGENTEX_BASE_URL", "http://localhost:5003")
AGENTEX_TIMEOUT = float(os.getenv("AGENTEX_TIMEOUT", "2.0"))


def is_agentex_available() -> bool:
    """Check if AgentEx infrastructure is available."""
    try:
        import httpx

        response = httpx.get(f"{AGENTEX_BASE_URL}/healthz", timeout=AGENTEX_TIMEOUT)
        return response.status_code == 200
    except Exception:
        return False


@pytest.fixture(scope="function")
def real_agentex_client():
    """
    Sync AgentEx client for testing sync agents.

    Prerequisites:
        - AgentEx services running (make dev)
        - At least one sync agent registered

    Usage:
        def test_sync_agent(real_agentex_client):
            agents = real_agentex_client.agents.list()
            # Test your sync agent
    """
    if not is_agentex_available():
        pytest.skip(f"AgentEx not available at {AGENTEX_BASE_URL}. Run 'make dev' or set AGENTEX_BASE_URL.")

    client = Agentex(api_key="test", base_url=AGENTEX_BASE_URL)
    yield client


@pytest_asyncio.fixture(scope="function")
async def real_agentex_async_client():
    """
    Async AgentEx client for testing agentic/temporal agents.

    Prerequisites:
        - AgentEx services running
        - At least one agentic/temporal agent registered

    Usage:
        @pytest.mark.asyncio
        async def test_agentic(real_agentex_async_client):
            agents = await real_agentex_async_client.agents.list()
            # Test your agentic agent
    """
    if not is_agentex_available():
        pytest.skip(f"AgentEx not available at {AGENTEX_BASE_URL}. Run 'make dev' or set AGENTEX_BASE_URL.")

    client = AsyncAgentex(api_key="test", base_url=AGENTEX_BASE_URL)
    yield client


@pytest_asyncio.fixture
async def sync_agent(real_agentex_async_client):
    """
    Provide a sync agent for testing.

    Returns first available sync agent from the system.
    """
    agents = await real_agentex_async_client.agents.list()
    if not agents:
        pytest.skip("No agents available. Run a tutorial agent first.")

    # Find sync agents
    sync_agents = [a for a in agents if a and hasattr(a, "acp_type") and a.acp_type == "sync"]

    if not sync_agents:
        pytest.skip("No sync agents available. Run a sync tutorial agent first.")

    yield sync_agents[0]


@pytest_asyncio.fixture
async def agentic_agent(real_agentex_async_client):
    """
    Provide an agentic agent for testing.

    Returns first available agentic agent from the system.
    """
    agents = await real_agentex_async_client.agents.list()
    if not agents:
        pytest.skip("No agents available. Run a tutorial agent first.")

    # Find agentic agents
    agentic_agents = [a for a in agents if a and hasattr(a, "acp_type") and a.acp_type == "agentic"]

    if not agentic_agents:
        pytest.skip("No agentic agents available. Run an agentic tutorial agent first.")

    yield agentic_agents[0]
