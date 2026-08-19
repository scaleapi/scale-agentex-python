"""Tests for per-tool-call spans on the sync OpenAI-Agents path.

The defect these guard: a span emitted *after* a tool returns has ~zero width,
so the tool's real duration is invisible on a timeline even when it is recorded
as an attribute. These assert the span is opened before the tool runs and closed
after, and that tracing failures never propagate.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from agents.tool_context import ToolContext

from agentex.lib.adk._modules import _sync_tracing_hooks as hooks_mod

SyncTracingHooks = hooks_mod.SyncTracingHooks


def _tool_context(args: str = '{"query": "hi"}') -> ToolContext:
    return ToolContext(context=None, tool_name="search", tool_call_id="call_abc", tool_arguments=args)


def _tool(name: str = "search") -> MagicMock:
    tool = MagicMock()
    tool.name = name
    return tool


def _adk(span=None):
    adk = SimpleNamespace(tracing=SimpleNamespace(start_span=AsyncMock(return_value=span), end_span=AsyncMock()))
    return adk


# --------------------------------------------------------------------------- #
# Argument parsing
# --------------------------------------------------------------------------- #


def test_tool_arguments_valid_dict():
    assert SyncTracingHooks._tool_arguments(_tool_context('{"a": 1}')) == {"a": 1}


def test_tool_arguments_garbage_is_preserved_raw():
    assert SyncTracingHooks._tool_arguments(_tool_context("not json")) == {"raw": "not json"}


def test_tool_arguments_missing_is_empty():
    assert SyncTracingHooks._tool_arguments(SimpleNamespace()) == {}


# --------------------------------------------------------------------------- #
# Span lifecycle
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_no_trace_id_is_a_no_op(monkeypatch):
    adk = _adk()
    monkeypatch.setattr(hooks_mod, "_get_adk", lambda: adk)

    hooks = SyncTracingHooks()
    await hooks.on_tool_start(_tool_context(), MagicMock(), _tool())

    adk.tracing.start_span.assert_not_awaited()


@pytest.mark.asyncio
async def test_span_opens_with_arguments_and_parent(monkeypatch):
    span = MagicMock()
    adk = _adk(span)
    monkeypatch.setattr(hooks_mod, "_get_adk", lambda: adk)

    hooks = SyncTracingHooks(trace_id="tr1", parent_span_id="root1", task_id="task1")
    await hooks.on_tool_start(_tool_context(), MagicMock(), _tool())

    kwargs = adk.tracing.start_span.await_args.kwargs
    assert kwargs["name"] == "search"
    assert kwargs["parent_id"] == "root1"
    assert kwargs["input"] == {"arguments": {"query": "hi"}}


@pytest.mark.asyncio
async def test_span_closes_with_result(monkeypatch):
    span = MagicMock()
    adk = _adk(span)
    monkeypatch.setattr(hooks_mod, "_get_adk", lambda: adk)

    hooks = SyncTracingHooks(trace_id="tr1")
    await hooks.on_tool_start(_tool_context(), MagicMock(), _tool())
    await hooks.on_tool_end(_tool_context(), MagicMock(), _tool(), "42 rows")

    assert span.output == {"result": "42 rows"}
    adk.tracing.end_span.assert_awaited_once()
    assert hooks._tool_spans == {}


@pytest.mark.asyncio
async def test_result_is_truncated(monkeypatch):
    span = MagicMock()
    adk = _adk(span)
    monkeypatch.setattr(hooks_mod, "_get_adk", lambda: adk)

    hooks = SyncTracingHooks(trace_id="tr1")
    await hooks.on_tool_start(_tool_context(), MagicMock(), _tool())
    await hooks.on_tool_end(_tool_context(), MagicMock(), _tool(), "x" * 10_000)

    assert len(span.output["result"]) == hooks_mod._MAX_SPAN_OUTPUT_CHARS


@pytest.mark.asyncio
async def test_end_without_start_is_a_no_op(monkeypatch):
    adk = _adk()
    monkeypatch.setattr(hooks_mod, "_get_adk", lambda: adk)

    hooks = SyncTracingHooks(trace_id="tr1")
    await hooks.on_tool_end(_tool_context(), MagicMock(), _tool(), "result")

    adk.tracing.end_span.assert_not_awaited()


@pytest.mark.asyncio
async def test_start_span_failure_does_not_propagate(monkeypatch):
    adk = _adk()
    adk.tracing.start_span.side_effect = RuntimeError("tracing backend down")
    monkeypatch.setattr(hooks_mod, "_get_adk", lambda: adk)

    hooks = SyncTracingHooks(trace_id="tr1")
    await hooks.on_tool_start(_tool_context(), MagicMock(), _tool())

    assert hooks._tool_spans == {}


@pytest.mark.asyncio
async def test_end_span_failure_does_not_propagate(monkeypatch):
    span = MagicMock()
    adk = _adk(span)
    adk.tracing.end_span.side_effect = RuntimeError("tracing backend down")
    monkeypatch.setattr(hooks_mod, "_get_adk", lambda: adk)

    hooks = SyncTracingHooks(trace_id="tr1")
    await hooks.on_tool_start(_tool_context(), MagicMock(), _tool())
    await hooks.on_tool_end(_tool_context(), MagicMock(), _tool(), "result")


@pytest.mark.asyncio
async def test_orphaned_spans_are_drained(monkeypatch):
    span = MagicMock()
    adk = _adk(span)
    monkeypatch.setattr(hooks_mod, "_get_adk", lambda: adk)

    hooks = SyncTracingHooks(trace_id="tr1")
    await hooks.on_tool_start(_tool_context(), MagicMock(), _tool())
    await hooks.close_open_tool_spans()

    assert span.output["incomplete"] is True
    adk.tracing.end_span.assert_awaited_once()
    assert hooks._tool_spans == {}
