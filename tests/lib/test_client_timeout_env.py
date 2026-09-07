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

from agentex.lib.adk.utils._modules.client import (
    _timeout_from_env,
    create_async_agentex_client,
)


def test_defaults_match_the_sdk_default_timeout():
    """An unconfigured process must behave exactly as it did before."""
    timeout = _timeout_from_env()
    assert timeout.connect == 5.0
    assert timeout.read == 300.0
    assert timeout.write == 300.0
    assert timeout.pool == 300.0


def test_connect_timeout_is_configurable(monkeypatch):
    monkeypatch.setenv("AGENTEX_CLIENT_CONNECT_TIMEOUT_SECONDS", "30")
    timeout = _timeout_from_env()
    assert timeout.connect == 30.0
    # the others are untouched
    assert timeout.read == 300.0


def test_all_four_are_configurable(monkeypatch):
    monkeypatch.setenv("AGENTEX_CLIENT_CONNECT_TIMEOUT_SECONDS", "30")
    monkeypatch.setenv("AGENTEX_CLIENT_READ_TIMEOUT_SECONDS", "120")
    monkeypatch.setenv("AGENTEX_CLIENT_WRITE_TIMEOUT_SECONDS", "90")
    monkeypatch.setenv("AGENTEX_CLIENT_POOL_TIMEOUT_SECONDS", "60")
    timeout = _timeout_from_env()
    assert (timeout.connect, timeout.read, timeout.write, timeout.pool) == (
        30.0,
        120.0,
        90.0,
        60.0,
    )


def test_an_empty_value_falls_back_to_the_default():
    """An unset variable and one set to the empty string mean the same thing."""
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("AGENTEX_CLIENT_CONNECT_TIMEOUT_SECONDS", "")
        assert _timeout_from_env().connect == 5.0


def test_client_picks_up_the_env_timeout(monkeypatch):
    monkeypatch.setenv("AGENTEX_CLIENT_CONNECT_TIMEOUT_SECONDS", "30")
    client = create_async_agentex_client(api_key="test", base_url="http://localhost:5003")
    # client.timeout is float | Timeout | None; narrow before reading a component.
    assert isinstance(client.timeout, httpx.Timeout)
    assert client.timeout.connect == 30.0


def test_explicit_timeout_wins_over_the_environment(monkeypatch):
    monkeypatch.setenv("AGENTEX_CLIENT_CONNECT_TIMEOUT_SECONDS", "30")
    client = create_async_agentex_client(
        api_key="test",
        base_url="http://localhost:5003",
        timeout=httpx.Timeout(connect=7.0, read=8.0, write=9.0, pool=10.0),
    )
    assert isinstance(client.timeout, httpx.Timeout)
    assert client.timeout.connect == 7.0


def test_env_auth_is_still_attached():
    """The factory's original job must survive the change."""
    client = create_async_agentex_client(api_key="test", base_url="http://localhost:5003")
    assert client._client.auth is not None


def test_a_bad_value_names_the_variable(monkeypatch):
    """A malformed value is a configuration error, so it must not be swallowed."""
    monkeypatch.setenv("AGENTEX_CLIENT_CONNECT_TIMEOUT_SECONDS", "not-a-number")
    with pytest.raises(ValueError, match="AGENTEX_CLIENT_CONNECT_TIMEOUT_SECONDS"):
        _timeout_from_env()


def test_the_timeout_does_not_depend_on_the_shared_environment_model(monkeypatch):
    """Regression: these must not become EnvironmentVariables fields.

    That model has required fields, is loaded by worker startup and by
    EnvAuth.auth_flow on every request, and agentex.lib.adk.utils builds a
    client at import time. Routing timeouts through it makes all three depend
    on a fully configured environment.
    """
    monkeypatch.delenv("AGENT_NAME", raising=False)
    monkeypatch.delenv("ACP_URL", raising=False)
    assert _timeout_from_env().connect == 5.0
