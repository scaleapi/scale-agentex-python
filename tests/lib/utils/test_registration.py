"""Startup registration metadata and credential compatibility."""

from __future__ import annotations

import os
import json
from unittest.mock import AsyncMock, call

import httpx
import pytest

from agentex.lib.utils import registration
from agentex.lib.utils.registration import register_agent, build_registration_metadata
from agentex.lib.environment_variables import EnvironmentVariables

SHA = "b362b171a9c4e1f09d8e7a6b5c4d3e2f1a0b9c8d"


def _env(**overrides) -> EnvironmentVariables:
    return EnvironmentVariables(AGENT_NAME="sample-agent", ACP_URL="http://agent", **overrides)


def test_nothing_known_yields_empty_metadata():
    assert build_registration_metadata(_env()) == {}


def test_commit_and_repo_reported_when_set():
    env = _env(AGENT_COMMIT_SHA=SHA, AGENT_SOURCE_REPO="git@github.com:scaleapi/Demo.git")
    assert build_registration_metadata(env) == {
        "commit_sha": SHA,
        "source_repo": "github.com/scaleapi/Demo",
    }


@pytest.mark.parametrize("value", ["latest", "v1.2.3", "rocket_mock_agent-" + SHA, "abc", "   "])
def test_non_commit_values_are_omitted_not_forwarded(value):
    """A field named for a commit never holds an image tag, same rule as __commit_sha__."""
    assert "commit_sha" not in build_registration_metadata(_env(AGENT_COMMIT_SHA=value))


def test_repo_normalization_strips_scheme_and_credentials():
    env = _env(AGENT_SOURCE_REPO="https://x-token:secret@GitHub.com/scaleapi/Demo.git")
    assert build_registration_metadata(env)["source_repo"] == "github.com/scaleapi/Demo"


def test_deployment_id_and_agent_card_still_reported():
    class Card:
        def model_dump(self):
            return {"name": "sample"}

    env = _env(AGENTEX_DEPLOYMENT_ID="dep-1")
    assert build_registration_metadata(env, Card()) == {
        "deployment_id": "dep-1",
        "agent_card": {"name": "sample"},
    }


@pytest.fixture
def registration_env(monkeypatch):
    for name in ("AGENT_ID", "AGENT_NAME", "AGENT_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(registration, "refreshed_environment_variables", None, raising=False)
    return _env(AGENTEX_BASE_URL="https://agentex.example.test/")


@pytest.fixture
def retry_sleep(monkeypatch):
    sleep = AsyncMock()
    monkeypatch.setattr(registration.asyncio, "sleep", sleep)
    return sleep


def _success(**overrides):
    return httpx.Response(200, json={"id": "agent-1", "name": "sample-agent", **overrides})


@pytest.mark.parametrize("configured_key", [None, "", "configured-agent-key"])
@pytest.mark.parametrize("response_key", [{}, {"agent_api_key": None}, {"agent_api_key": ""}])
async def test_registration_preserves_configured_key_when_response_has_no_key(
    registration_env, respx_mock, configured_key, response_key
):
    registration_env.AGENT_API_KEY = configured_key
    if configured_key is not None:
        os.environ["AGENT_API_KEY"] = configured_key
    route = respx_mock.post("https://agentex.example.test/agents/register").mock(return_value=_success(**response_key))

    await register_agent(registration_env)

    request = route.calls.last.request
    assert route.call_count == 1
    assert request.headers.get("x-agent-api-key") == (configured_key or None)
    assert "authorization" not in request.headers
    assert "agent_api_key" not in json.loads(request.content)
    assert registration_env.AGENT_API_KEY == configured_key
    assert os.environ.get("AGENT_API_KEY") == configured_key
    assert registration_env.AGENT_ID == os.environ["AGENT_ID"] == "agent-1"
    assert registration_env.AGENT_NAME == os.environ["AGENT_NAME"] == "sample-agent"


@pytest.mark.parametrize("configured_key", [None, "older-agent-key"])
async def test_registration_accepts_returned_key(registration_env, respx_mock, configured_key):
    registration_env.AGENT_API_KEY = configured_key
    route = respx_mock.post("https://agentex.example.test/agents/register").mock(
        return_value=_success(agent_api_key="returned-agent-key")
    )

    await register_agent(registration_env)

    assert route.calls.last.request.headers.get("x-agent-api-key") == configured_key
    assert registration_env.AGENT_API_KEY == os.environ["AGENT_API_KEY"] == "returned-agent-key"


@pytest.mark.parametrize("status", [401, 403])
async def test_rejected_registration_never_retries_anonymously(
    registration_env, respx_mock, retry_sleep, caplog, status
):
    key = "configured-agent-key"
    registration_env.AGENT_API_KEY = key
    os.environ["AGENT_API_KEY"] = key
    route = respx_mock.post("https://agentex.example.test/agents/register").mock(
        return_value=httpx.Response(status, text=f"Rejected credential: {key}")
    )

    with pytest.raises(RuntimeError, match=f"Status: {status}") as exc:
        await register_agent(registration_env)

    assert route.call_count == 3
    assert all(item.request.headers["x-agent-api-key"] == key for item in route.calls)
    assert registration_env.AGENT_API_KEY == os.environ["AGENT_API_KEY"] == key
    assert registration_env.AGENT_ID is None
    assert "AGENT_ID" not in os.environ
    assert retry_sleep.await_args_list == [call(5), call(10)]
    assert key not in caplog.text
    assert key not in str(exc.value)


async def test_transient_failure_retries_with_configured_key(registration_env, respx_mock, retry_sleep):
    registration_env.AGENT_API_KEY = "configured-agent-key"
    route = respx_mock.post("https://agentex.example.test/agents/register").mock(
        side_effect=[httpx.Response(503), _success(agent_api_key="returned-agent-key")]
    )

    await register_agent(registration_env)

    assert route.call_count == 2
    assert all(item.request.headers["x-agent-api-key"] == "configured-agent-key" for item in route.calls)
    assert registration_env.AGENT_API_KEY == os.environ["AGENT_API_KEY"] == "returned-agent-key"
    retry_sleep.assert_awaited_once_with(5)


async def test_transport_error_does_not_expose_credential(registration_env, respx_mock, retry_sleep, caplog):
    key = "configured-agent-key"
    registration_env.AGENT_API_KEY = key
    route = respx_mock.post("https://agentex.example.test/agents/register").mock(
        side_effect=httpx.ReadTimeout(f"Timeout sending {key}")
    )

    with pytest.raises(RuntimeError, match="ReadTimeout") as exc:
        await register_agent(registration_env)

    assert route.call_count == 3
    assert all(item.request.headers["x-agent-api-key"] == key for item in route.calls)
    assert key not in caplog.text
    assert key not in str(exc.value)
    assert exc.value.__context__ is None


async def test_success_does_not_log_registration_payload(registration_env, respx_mock, caplog):
    registration_env.AGENT_API_KEY = "configured-agent-key"
    registration_env.AGENT_DESCRIPTION = "private-description"
    respx_mock.post("https://agentex.example.test/agents/register").mock(
        return_value=_success(agent_api_key="returned-agent-key")
    )

    await register_agent(registration_env, agent_card={"name": "private-card"})

    assert "Successfully registered agent" in caplog.text
    for value in ("configured-agent-key", "returned-agent-key", "private-description", "private-card"):
        assert value not in caplog.text


@pytest.mark.parametrize("returned_key", [123, {"value": "not-a-string"}])
async def test_invalid_returned_key_does_not_overwrite_configuration(
    registration_env, respx_mock, retry_sleep, returned_key
):
    registration_env.AGENT_API_KEY = "configured-agent-key"
    os.environ["AGENT_API_KEY"] = "configured-agent-key"
    respx_mock.post("https://agentex.example.test/agents/register").mock(
        return_value=_success(agent_api_key=returned_key)
    )

    with pytest.raises(RuntimeError, match="ValueError"):
        await register_agent(registration_env)

    assert registration_env.AGENT_API_KEY == os.environ["AGENT_API_KEY"] == "configured-agent-key"
    assert registration_env.AGENT_ID is None
    assert "AGENT_ID" not in os.environ


async def test_missing_base_url_skips_registration(registration_env, respx_mock):
    registration_env.AGENTEX_BASE_URL = None

    await register_agent(registration_env)

    assert not respx_mock.calls
