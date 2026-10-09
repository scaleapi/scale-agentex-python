"""Tests for wait_for_state_messages in the tutorials' test_utils.

The tutorials' `test_utils` package shares its name with `tests/test_utils`, so the
module is loaded from its file path instead of imported by name.
"""

from __future__ import annotations

import time
import importlib.util
from types import ModuleType, SimpleNamespace
from pathlib import Path

import pytest

_ASYNC_UTILS = Path(__file__).resolve().parents[2] / "examples" / "tutorials" / "test_utils" / "async_utils.py"


def _load_async_utils() -> ModuleType:
    spec = importlib.util.spec_from_file_location("tutorial_async_utils", _ASYNC_UTILS)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


wait_for_state_messages = _load_async_utils().wait_for_state_messages


class _FakeStates:
    """Returns one state whose message count grows from 1 to 3 once `write_after` seconds pass."""

    def __init__(self, write_after: float | None):
        self._start = time.monotonic()
        self._write_after = write_after
        self.calls = 0

    async def list(self, agent_id: str, task_id: str) -> list[SimpleNamespace]:
        del agent_id, task_id
        self.calls += 1
        written = self._write_after is not None and time.monotonic() - self._start >= self._write_after
        return [SimpleNamespace(state={"messages": [{"role": "system"}] * (3 if written else 1)})]


def _client(write_after: float | None) -> SimpleNamespace:
    return SimpleNamespace(states=_FakeStates(write_after))


@pytest.mark.asyncio
async def test_waits_for_a_state_write_that_lands_after_the_reply() -> None:
    client = _client(write_after=0.3)

    messages = await wait_for_state_messages(client, "agent", "task", expected_count=3, timeout=5, sleep_interval=0.05)

    assert len(messages) == 3
    assert client.states.calls > 1


@pytest.mark.asyncio
async def test_returns_the_real_state_at_the_deadline_when_it_never_updates() -> None:
    client = _client(write_after=None)
    start = time.monotonic()

    messages = await wait_for_state_messages(client, "agent", "task", expected_count=3, timeout=0.3, sleep_interval=0.05)

    # It kept polling until the deadline instead of returning early. No upper bound:
    # a busy worker may wake late, and returning at all already proves it stopped.
    assert len(messages) == 1
    assert time.monotonic() - start >= 0.3


@pytest.mark.asyncio
async def test_returns_on_the_first_poll_when_the_state_is_already_written() -> None:
    client = _client(write_after=0)

    messages = await wait_for_state_messages(client, "agent", "task", expected_count=3)

    assert len(messages) == 3
    assert client.states.calls == 1
