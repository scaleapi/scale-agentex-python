"""Tests for the unified OpenAI-Agents turn surface.

Covers:
- ``TemporalStreamingHooks`` message-emission gating (``emit_messages``), so the
  streaming model can be the sole tool-message emitter (no double-post).
- ``TemporalStreamingHooks`` input-bearing tool spans (input = arguments,
  output = result) when a ``trace_id`` is provided.
- ``run_turn`` usage extraction and default-hooks wiring.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from agents.tool_context import ToolContext

from agentex.lib.core.temporal.plugins.openai_agents import run as run_mod
from agentex.lib.core.temporal.plugins.openai_agents.hooks import hooks as hooks_mod

TemporalStreamingHooks = hooks_mod.TemporalStreamingHooks


def _tool_context(args: str = '{"query": "hi"}') -> ToolContext:
    return ToolContext(
        context=None,
        tool_name="search",
        tool_call_id="call_abc",
        tool_arguments=args,
    )


def _tool() -> MagicMock:
    tool = MagicMock()
    tool.name = "search"
    return tool


# --------------------------------------------------------------------------- #
# Argument parsing
# --------------------------------------------------------------------------- #


def test_parse_tool_arguments_valid_dict():
    assert TemporalStreamingHooks._parse_tool_arguments(_tool_context('{"a": 1}')) == {"a": 1}


def test_parse_tool_arguments_garbage_is_empty():
    assert TemporalStreamingHooks._parse_tool_arguments(_tool_context("not json")) == {}


def test_parse_tool_arguments_non_tool_context_is_empty():
    assert TemporalStreamingHooks._parse_tool_arguments(SimpleNamespace()) == {}


# --------------------------------------------------------------------------- #
# Message emission gating (the double-post fix)
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_emit_messages_true_streams_tool_request(monkeypatch):
    exec_activity = AsyncMock()
    monkeypatch.setattr(hooks_mod.workflow, "execute_activity", exec_activity)

    hooks = TemporalStreamingHooks(task_id="t1", emit_messages=True)
    await hooks.on_tool_start(_tool_context(), MagicMock(), _tool())

    exec_activity.assert_awaited_once()
    # args=[task_id, ToolRequestContent.model_dump()]
    _, kwargs = exec_activity.call_args
    payload = kwargs["args"][1]
    assert payload["name"] == "search"
    assert payload["arguments"] == {"query": "hi"}


@pytest.mark.asyncio
async def test_emit_messages_false_skips_tool_request(monkeypatch):
    exec_activity = AsyncMock()
    monkeypatch.setattr(hooks_mod.workflow, "execute_activity", exec_activity)

    hooks = TemporalStreamingHooks(task_id="t1", emit_messages=False)
    await hooks.on_tool_start(_tool_context(), MagicMock(), _tool())
    await hooks.on_tool_end(_tool_context(), MagicMock(), _tool(), "result")

    exec_activity.assert_not_awaited()


@pytest.mark.asyncio
async def test_emit_messages_false_skips_handoff(monkeypatch):
    exec_activity = AsyncMock()
    monkeypatch.setattr(hooks_mod.workflow, "execute_activity", exec_activity)

    hooks = TemporalStreamingHooks(task_id="t1", emit_messages=False)
    await hooks.on_handoff(MagicMock(), MagicMock(name="from"), MagicMock(name="to"))

    exec_activity.assert_not_awaited()


# --------------------------------------------------------------------------- #
# Input-bearing tool spans (the "traces have outputs but no inputs" fix)
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_tool_span_carries_input_and_output(monkeypatch):
    monkeypatch.setattr(hooks_mod.workflow, "execute_activity", AsyncMock())
    span = SimpleNamespace(output=None)
    start_span = AsyncMock(return_value=span)
    end_span = AsyncMock()
    fake_adk = SimpleNamespace(tracing=SimpleNamespace(start_span=start_span, end_span=end_span))
    monkeypatch.setattr(hooks_mod, "_get_adk", lambda: fake_adk)

    hooks = TemporalStreamingHooks(task_id="t1", emit_messages=False, trace_id="trace-1", parent_span_id="parent-1")
    await hooks.on_tool_start(_tool_context(), MagicMock(), _tool())

    start_span.assert_awaited_once()
    _, kwargs = start_span.call_args
    assert kwargs["name"] == "tool:search"
    assert kwargs["parent_id"] == "parent-1"
    assert kwargs["input"] == {"arguments": {"query": "hi"}}

    await hooks.on_tool_end(_tool_context(), MagicMock(), _tool(), "the answer")
    end_span.assert_awaited_once()
    assert span.output == {"result": "the answer"}


@pytest.mark.asyncio
async def test_no_trace_id_means_no_span(monkeypatch):
    monkeypatch.setattr(hooks_mod.workflow, "execute_activity", AsyncMock())
    start_span = AsyncMock()
    fake_adk = SimpleNamespace(tracing=SimpleNamespace(start_span=start_span))
    monkeypatch.setattr(hooks_mod, "_get_adk", lambda: fake_adk)

    hooks = TemporalStreamingHooks(task_id="t1", emit_messages=False, trace_id=None)
    await hooks.on_tool_start(_tool_context(), MagicMock(), _tool())

    start_span.assert_not_awaited()


# --------------------------------------------------------------------------- #
# Usage extraction
# --------------------------------------------------------------------------- #


def _result_with_usage() -> SimpleNamespace:
    usage = SimpleNamespace(
        requests=3,
        input_tokens=100,
        output_tokens=40,
        total_tokens=140,
        input_tokens_details=SimpleNamespace(cached_tokens=20),
        output_tokens_details=SimpleNamespace(reasoning_tokens=10),
    )
    return SimpleNamespace(context_wrapper=SimpleNamespace(usage=usage), final_output="done")


def test_extract_turn_usage_maps_fields():
    usage = run_mod._extract_turn_usage(_result_with_usage(), model="openai/gpt-5.5")
    assert usage.model == "openai/gpt-5.5"
    assert usage.input_tokens == 100
    assert usage.output_tokens == 40
    assert usage.total_tokens == 140
    assert usage.cached_input_tokens == 20
    assert usage.reasoning_tokens == 10
    assert usage.num_llm_calls == 3


def test_extract_turn_usage_missing_usage_is_tolerant():
    usage = run_mod._extract_turn_usage(SimpleNamespace(), model="m")
    assert usage.model == "m"
    assert usage.input_tokens is None
    assert usage.num_llm_calls is None


# --------------------------------------------------------------------------- #
# run_turn
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_run_turn_returns_usage_and_passes_through_result(monkeypatch):
    fake_result = _result_with_usage()
    runner_run = AsyncMock(return_value=fake_result)
    monkeypatch.setattr(run_mod.Runner, "run", runner_run)

    agent = SimpleNamespace(model="openai/gpt-5.5")
    out = await run_mod.run_turn(
        agent,
        [{"role": "user", "content": "hi"}],
        task_id="t1",
        trace_id="trace-1",
        parent_span_id="parent-1",
    )

    assert isinstance(out, run_mod.OpenAIAgentsTurnResult)
    assert out.final_output == "done"
    assert out.usage.total_tokens == 140
    assert out.usage.model == "openai/gpt-5.5"

    # Default hooks must be wired so the streaming model is the sole emitter.
    runner_run.assert_awaited_once()
    _, kwargs = runner_run.call_args
    hooks = kwargs["hooks"]
    assert hooks.emit_messages is False
    assert hooks.trace_id == "trace-1"
    assert hooks.parent_span_id == "parent-1"


@pytest.mark.asyncio
async def test_run_turn_respects_supplied_hooks(monkeypatch):
    runner_run = AsyncMock(return_value=_result_with_usage())
    monkeypatch.setattr(run_mod.Runner, "run", runner_run)

    custom_hooks = TemporalStreamingHooks(task_id="t1", emit_messages=False)
    await run_mod.run_turn(
        SimpleNamespace(model="m"),
        "hi",
        task_id="t1",
        hooks=custom_hooks,
    )

    _, kwargs = runner_run.call_args
    assert kwargs["hooks"] is custom_hooks
