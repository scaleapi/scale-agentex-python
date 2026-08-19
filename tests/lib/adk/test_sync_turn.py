"""Tests for the root turn span on the sync OpenAI-Agents path.

The defect these guard: with no root span and no parenting, a trace is a flat
list of fragments whose durations do not sum to the turn, so tool time simply
goes missing. These assert a root span exists, that tool spans hang off it, and
that tracing failures never stop the turn from streaming.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from agentex.lib.adk._modules import _sync_turn as turn_mod


def _adk(root_span=None):
    return SimpleNamespace(
        tracing=SimpleNamespace(
            start_span=AsyncMock(return_value=root_span),
            end_span=AsyncMock(),
        )
    )


def _runner_yielding(*events):
    async def _stream():
        for e in events:
            yield e

    result = MagicMock()
    result.stream_events = _stream
    return MagicMock(return_value=result)


def _agent(name="analyst"):
    agent = MagicMock()
    agent.name = name
    return agent


async def _drain(gen):
    return [e async for e in gen]


@pytest.mark.asyncio
async def test_opens_a_root_span_and_closes_it(monkeypatch):
    root = SimpleNamespace(id="root-1")
    adk = _adk(root)
    monkeypatch.setattr(turn_mod, "_get_adk", lambda: adk)
    monkeypatch.setattr(turn_mod.Runner, "run_streamed", _runner_yielding("a", "b"))

    events = await _drain(turn_mod.run_turn_streamed(_agent(), [], trace_id="tr1", task_id="task1"))

    assert events == ["a", "b"]
    assert adk.tracing.start_span.await_args.kwargs["name"] == "turn"
    adk.tracing.end_span.assert_awaited_once()
    assert adk.tracing.end_span.await_args.kwargs["span"] is root


@pytest.mark.asyncio
async def test_tool_spans_are_parented_to_the_root(monkeypatch):
    root = SimpleNamespace(id="root-1")
    monkeypatch.setattr(turn_mod, "_get_adk", lambda: _adk(root))

    captured = {}

    class _Hooks:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        async def close_open_tool_spans(self):
            return None

    monkeypatch.setattr(turn_mod, "SyncTracingHooks", _Hooks)
    monkeypatch.setattr(turn_mod.Runner, "run_streamed", _runner_yielding("a"))

    await _drain(turn_mod.run_turn_streamed(_agent(), [], trace_id="tr1"))

    assert captured["parent_span_id"] == "root-1"


@pytest.mark.asyncio
async def test_no_trace_id_still_streams(monkeypatch):
    adk = _adk()
    monkeypatch.setattr(turn_mod, "_get_adk", lambda: adk)
    monkeypatch.setattr(turn_mod.Runner, "run_streamed", _runner_yielding("a", "b"))

    events = await _drain(turn_mod.run_turn_streamed(_agent(), []))

    assert events == ["a", "b"]
    adk.tracing.start_span.assert_not_awaited()


@pytest.mark.asyncio
async def test_start_span_failure_still_streams(monkeypatch):
    adk = _adk()
    adk.tracing.start_span.side_effect = RuntimeError("tracing backend down")
    monkeypatch.setattr(turn_mod, "_get_adk", lambda: adk)
    monkeypatch.setattr(turn_mod.Runner, "run_streamed", _runner_yielding("a"))

    assert await _drain(turn_mod.run_turn_streamed(_agent(), [], trace_id="tr1")) == ["a"]


@pytest.mark.asyncio
async def test_root_span_closes_when_the_run_raises(monkeypatch):
    root = SimpleNamespace(id="root-1")
    adk = _adk(root)
    monkeypatch.setattr(turn_mod, "_get_adk", lambda: adk)

    async def _boom():
        yield "a"
        raise RuntimeError("max turns exceeded")

    result = MagicMock()
    result.stream_events = _boom
    monkeypatch.setattr(turn_mod.Runner, "run_streamed", MagicMock(return_value=result))

    with pytest.raises(RuntimeError):
        await _drain(turn_mod.run_turn_streamed(_agent(), [], trace_id="tr1"))

    adk.tracing.end_span.assert_awaited_once()
