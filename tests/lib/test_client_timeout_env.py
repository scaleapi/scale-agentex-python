"""Timeouts for the AgentEx client are configurable by environment variable.

The connect timeout is the one that matters in practice. An AgentEx backend
accepts connections serially, so connect latency grows with the number of
concurrent callers, and the 5s default is reached once a few hundred are in
flight. Before this was configurable, the only way to change it was to pass
``timeout=`` at every construction site, which application code cannot do for
the client the ADK builds internally.
"""

from __future__ import annotations

import httpx
import pytest

import agentex.lib.environment_variables as env_module
from agentex.lib.adk.utils._modules.client import (
    _timeout_from_env,
    create_async_agentex_client,
)
from agentex.lib.environment_variables import EnvironmentVariables


@pytest.fixture(autouse=True)
def _clear_env_cache():
    """EnvironmentVariables.refresh() memoises into a module global."""
    env_module.refreshed_environment_variables = None
    yield
    env_module.refreshed_environment_variables = None


def _set_env(monkeypatch, **overrides: str) -> None:
    # EnvironmentVariables has required fields; set them so construction succeeds.
    monkeypatch.setenv("AGENT_NAME", "test-agent")
    monkeypatch.setenv("ACP_URL", "http://localhost:8000")
    for key, value in overrides.items():
        monkeypatch.setenv(key, value)


def test_defaults_match_the_sdk_default_timeout(monkeypatch):
    """An unconfigured process must behave exactly as it did before."""
    _set_env(monkeypatch)
    timeout = _timeout_from_env()
    assert timeout.connect == 5.0
    assert timeout.read == 300.0
    assert timeout.write == 300.0
    assert timeout.pool == 300.0


def test_connect_timeout_is_configurable(monkeypatch):
    _set_env(monkeypatch, AGENTEX_CLIENT_CONNECT_TIMEOUT_SECONDS="30")
    timeout = _timeout_from_env()
    assert timeout.connect == 30.0
    # the others are untouched
    assert timeout.read == 300.0


def test_all_four_are_configurable(monkeypatch):
    _set_env(
        monkeypatch,
        AGENTEX_CLIENT_CONNECT_TIMEOUT_SECONDS="30",
        AGENTEX_CLIENT_READ_TIMEOUT_SECONDS="120",
        AGENTEX_CLIENT_WRITE_TIMEOUT_SECONDS="90",
        AGENTEX_CLIENT_POOL_TIMEOUT_SECONDS="60",
    )
    timeout = _timeout_from_env()
    assert (timeout.connect, timeout.read, timeout.write, timeout.pool) == (
        30.0,
        120.0,
        90.0,
        60.0,
    )


def test_client_picks_up_the_env_timeout(monkeypatch):
    _set_env(monkeypatch, AGENTEX_CLIENT_CONNECT_TIMEOUT_SECONDS="30")
    client = create_async_agentex_client(api_key="test", base_url="http://localhost:5003")
    assert client.timeout.connect == 30.0


def test_explicit_timeout_wins_over_the_environment(monkeypatch):
    _set_env(monkeypatch, AGENTEX_CLIENT_CONNECT_TIMEOUT_SECONDS="30")
    client = create_async_agentex_client(
        api_key="test",
        base_url="http://localhost:5003",
        timeout=httpx.Timeout(connect=7.0, read=8.0, write=9.0, pool=10.0),
    )
    assert client.timeout.connect == 7.0


def test_env_auth_is_still_attached(monkeypatch):
    """The factory's original job must survive the change."""
    _set_env(monkeypatch)
    client = create_async_agentex_client(api_key="test", base_url="http://localhost:5003")
    assert client._client.auth is not None


def test_a_bad_value_does_not_prevent_client_creation(monkeypatch):
    """Timeout configuration must never be the reason a client fails to build."""
    _set_env(monkeypatch, AGENTEX_CLIENT_CONNECT_TIMEOUT_SECONDS="not-a-number")
    client = create_async_agentex_client(api_key="test", base_url="http://localhost:5003")
    assert client is not None
