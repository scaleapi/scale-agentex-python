"""AgentexWorker wires the backend version guard into worker startup.

A Temporal worker runs as its own process and never goes through the ACP server
lifespan, so the guard must run inside `_register_agent` — before `register_agent`,
and only when `AGENTEX_BASE_URL` is set.
"""

from __future__ import annotations

from unittest.mock import Mock, AsyncMock

import pytest

from agentex.lib.core.temporal.workers import worker as worker_mod
from agentex.lib.core.compat.version_guard import IncompatibleBackendError


def _worker():
    # explicit health_check_port so __init__ doesn't read EnvironmentVariables
    return worker_mod.AgentexWorker(task_queue="test-queue", health_check_port=8080)


def _patch_env(monkeypatch, base_url):
    env = Mock()
    env.AGENTEX_BASE_URL = base_url
    fake_cls = Mock()
    fake_cls.refresh.return_value = env
    monkeypatch.setattr(worker_mod, "EnvironmentVariables", fake_cls)
    return env


async def test_guard_runs_before_register_agent(monkeypatch):
    env = _patch_env(monkeypatch, "http://backend")
    order: list[str] = []
    guard = AsyncMock(side_effect=lambda *a, **k: order.append("guard"))
    register = AsyncMock(side_effect=lambda *a, **k: order.append("register"))
    monkeypatch.setattr(worker_mod, "assert_backend_compatible", guard)
    monkeypatch.setattr(worker_mod, "register_agent", register)

    await _worker()._register_agent()

    guard.assert_awaited_once_with("http://backend")
    register.assert_awaited_once_with(env)
    assert order == ["guard", "register"]  # guard must precede registration


async def test_incompatible_backend_blocks_registration(monkeypatch):
    _patch_env(monkeypatch, "http://backend")
    guard = AsyncMock(side_effect=IncompatibleBackendError("backend too old"))
    register = AsyncMock()
    monkeypatch.setattr(worker_mod, "assert_backend_compatible", guard)
    monkeypatch.setattr(worker_mod, "register_agent", register)

    with pytest.raises(IncompatibleBackendError):
        await _worker()._register_agent()

    register.assert_not_awaited()  # fail fast — never register against an unsupported backend


async def test_no_base_url_skips_guard_and_registration(monkeypatch):
    _patch_env(monkeypatch, None)
    guard = AsyncMock()
    register = AsyncMock()
    monkeypatch.setattr(worker_mod, "assert_backend_compatible", guard)
    monkeypatch.setattr(worker_mod, "register_agent", register)

    await _worker()._register_agent()

    guard.assert_not_awaited()
    register.assert_not_awaited()
