"""Tests for the runtime server-version compatibility check (AGX1-367)."""

from __future__ import annotations

import logging

import httpx
import pytest

import agentex.lib._server_compat as sc
from agentex.lib._server_compat import (
    SERVER_VERSION_HEADER,
    install_on,
    check_server_version,
)
from agentex.lib.adk.utils._modules.client import create_async_agentex_client


@pytest.fixture(autouse=True)
def _reset_warned():
    sc._warned = False
    yield
    sc._warned = False


@pytest.fixture
def _floor_2(monkeypatch: pytest.MonkeyPatch):
    # Pin a known floor so the assertions don't depend on the shipped value.
    monkeypatch.setattr(sc, "MIN_SUPPORTED_SERVER_VERSION", "2.0.0")


def test_warns_once_when_server_below_floor(_floor_2, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        check_server_version("1.9.0")
        check_server_version("1.0.0")  # second call must not double-warn
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "1.9.0" in warnings[0].getMessage()


@pytest.mark.parametrize("version", ["2.0.0", "2.1.0", "10.0.0"])
def test_silent_when_server_at_or_above_floor(_floor_2, version: str, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        check_server_version(version)
    assert not [r for r in caplog.records if r.levelno == logging.WARNING]


@pytest.mark.parametrize("version", [None, "", "unknown"])
def test_silent_when_header_absent_or_unparseable(_floor_2, version, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        check_server_version(version)
    assert not [r for r in caplog.records if r.levelno == logging.WARNING]


def test_strict_mode_raises(_floor_2, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENTEX_STRICT_SERVER_VERSION", "1")
    with pytest.raises(RuntimeError, match="older than the minimum"):
        check_server_version("1.9.0")


def test_factory_installs_response_hook() -> None:
    client = create_async_agentex_client(base_url="http://test", api_key="test")
    assert client._client.event_hooks.get("response")


async def test_installed_hook_checks_header(_floor_2, caplog: pytest.LogCaptureFixture) -> None:
    http_client = httpx.AsyncClient()
    install_on(http_client)
    hook = http_client.event_hooks["response"][-1]
    response = httpx.Response(200, headers={SERVER_VERSION_HEADER: "1.0.0"})
    with caplog.at_level(logging.WARNING):
        await hook(response)
    assert [r for r in caplog.records if r.levelno == logging.WARNING]
