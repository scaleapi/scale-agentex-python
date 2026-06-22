"""Offline tests for CodexTurn and codex_usage_to_turn_usage.

Tests cover:
- TurnUsage normalization from raw codex usage dicts
- Defensive handling of missing/invalid usage fields
- CodexTurn: events property yields canonical StreamTaskMessage*
- CodexTurn: usage() before and after stream exhaustion
- CodexTurn: on_result wiring (session_id, counts propagate to usage())
- CodexTurn satisfies HarnessTurn protocol
"""

from __future__ import annotations

from typing import Any, AsyncIterator

import pytest

from agentex.lib.core.harness.types import TurnUsage, HarnessTurn
from agentex.types.task_message_update import (
    StreamTaskMessageDone,
    StreamTaskMessageFull,
    StreamTaskMessageDelta,
    StreamTaskMessageStart,
)
from agentex.lib.adk._modules._codex_turn import (
    CodexTurn,
    codex_usage_to_turn_usage,
)


async def _aiter(items: list[Any]) -> AsyncIterator[Any]:
    for item in items:
        yield item


async def _collect(turn: CodexTurn) -> list[Any]:
    return [msg async for msg in turn.events]


# ---------------------------------------------------------------------------
# codex_usage_to_turn_usage
# ---------------------------------------------------------------------------


class TestCodexUsageToTurnUsage:
    def test_none_raw_all_none_tokens(self) -> None:
        u = codex_usage_to_turn_usage(None)
        assert u.input_tokens is None
        assert u.output_tokens is None
        assert u.total_tokens is None
        assert u.cost_usd is None

    def test_empty_dict_all_none_tokens(self) -> None:
        u = codex_usage_to_turn_usage({})
        assert u.input_tokens is None
        assert u.output_tokens is None

    def test_standard_usage(self) -> None:
        raw = {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150}
        u = codex_usage_to_turn_usage(raw, model="o4-mini")
        assert u.input_tokens == 100
        assert u.output_tokens == 50
        assert u.total_tokens == 150
        assert u.model == "o4-mini"

    def test_reasoning_tokens(self) -> None:
        raw = {"input_tokens": 200, "output_tokens": 80, "reasoning_tokens": 60, "total_tokens": 340}
        u = codex_usage_to_turn_usage(raw)
        assert u.reasoning_tokens == 60

    def test_real_zero_preserved(self) -> None:
        """Explicit zeros in the payload must survive (not be treated as missing)."""
        raw = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
        u = codex_usage_to_turn_usage(raw)
        assert u.input_tokens == 0
        assert u.output_tokens == 0

    def test_cached_input_tokens(self) -> None:
        raw = {"input_tokens": 100, "cached_input_tokens": 20, "output_tokens": 40}
        u = codex_usage_to_turn_usage(raw)
        assert u.cached_input_tokens == 20

    def test_invalid_token_values_become_none(self) -> None:
        raw = {"input_tokens": "not_a_number", "output_tokens": None}
        u = codex_usage_to_turn_usage(raw)
        assert u.input_tokens is None
        assert u.output_tokens is None

    def test_cost_explicit(self) -> None:
        u = codex_usage_to_turn_usage(None, cost_usd=0.0042)
        assert u.cost_usd == pytest.approx(0.0042)

    def test_cost_from_raw(self) -> None:
        u = codex_usage_to_turn_usage({"cost_usd": 0.001})
        assert u.cost_usd == pytest.approx(0.001)

    def test_explicit_cost_overrides_raw(self) -> None:
        """Explicit cost_usd kwarg takes precedence over raw dict value."""
        u = codex_usage_to_turn_usage({"cost_usd": 0.001}, cost_usd=0.002)
        assert u.cost_usd == pytest.approx(0.002)

    def test_tool_and_reasoning_counts(self) -> None:
        u = codex_usage_to_turn_usage(None, tool_call_count=3, reasoning_count=2)
        assert u.num_tool_calls == 3
        assert u.num_reasoning_blocks == 2

    def test_num_llm_calls_always_one(self) -> None:
        u = codex_usage_to_turn_usage(None)
        assert u.num_llm_calls == 1

    def test_duration_ms(self) -> None:
        u = codex_usage_to_turn_usage(None, duration_ms=1234)
        assert u.duration_ms == 1234

    def test_model_none_when_not_provided(self) -> None:
        u = codex_usage_to_turn_usage(None)
        assert u.model is None

    def test_non_dict_raw_treated_as_empty(self) -> None:
        u = codex_usage_to_turn_usage("bad input")  # type: ignore[arg-type]
        assert u.input_tokens is None

    def test_returns_turn_usage_instance(self) -> None:
        u = codex_usage_to_turn_usage({})
        assert isinstance(u, TurnUsage)


# ---------------------------------------------------------------------------
# CodexTurn protocol conformance
# ---------------------------------------------------------------------------


class TestCodexTurnProtocol:
    def test_implements_harness_turn_protocol(self) -> None:
        turn = CodexTurn(_aiter([]), model="o4-mini")
        assert isinstance(turn, HarnessTurn)

    def test_usage_before_exhaustion_returns_zero_turn_usage(self) -> None:
        turn = CodexTurn(_aiter([]), model="test-model")
        u = turn.usage()
        assert isinstance(u, TurnUsage)
        assert u.model == "test-model"
        assert u.input_tokens is None
        assert u.num_tool_calls == 0


# ---------------------------------------------------------------------------
# CodexTurn events
# ---------------------------------------------------------------------------


class TestCodexTurnEvents:
    async def test_events_yield_stream_task_messages(self) -> None:
        events = [
            {"type": "item.started", "item": {"id": "m1", "type": "agent_message", "text": "hi"}},
            {"type": "item.completed", "item": {"id": "m1", "type": "agent_message", "text": "hi"}},
        ]
        turn = CodexTurn(_aiter(events), model="o4-mini")
        out = await _collect(turn)
        assert len(out) > 0
        for msg in out:
            assert isinstance(
                msg,
                (StreamTaskMessageStart, StreamTaskMessageDelta, StreamTaskMessageFull, StreamTaskMessageDone),
            )

    async def test_usage_after_exhaustion_has_tokens(self) -> None:
        events = [
            {
                "type": "turn.completed",
                "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
            }
        ]
        turn = CodexTurn(_aiter(events), model="o4-mini")
        await _collect(turn)
        u = turn.usage()
        assert u.input_tokens == 10
        assert u.output_tokens == 5
        assert u.total_tokens == 15

    async def test_usage_model_propagated(self) -> None:
        events = [{"type": "turn.completed", "usage": None}]
        turn = CodexTurn(_aiter(events), model="codex-model-x")
        await _collect(turn)
        assert turn.usage().model == "codex-model-x"

    async def test_tool_count_in_usage(self) -> None:
        events = [
            {
                "type": "item.started",
                "item": {"id": "t1", "type": "command_execution", "command": "ls"},
            },
            {
                "type": "item.completed",
                "item": {
                    "id": "t1",
                    "type": "command_execution",
                    "command": "ls",
                    "aggregated_output": ".",
                    "exit_code": 0,
                },
            },
            {"type": "turn.completed", "usage": None},
        ]
        turn = CodexTurn(_aiter(events), model="o4-mini")
        await _collect(turn)
        assert turn.usage().num_tool_calls == 1

    async def test_reasoning_count_in_usage(self) -> None:
        events = [
            {"type": "item.started", "item": {"id": "r1", "type": "reasoning", "text": ""}},
            {
                "type": "item.completed",
                "item": {"id": "r1", "type": "reasoning", "text": "thought"},
            },
            {"type": "turn.completed", "usage": None},
        ]
        turn = CodexTurn(_aiter(events), model="o4-mini")
        await _collect(turn)
        assert turn.usage().num_reasoning_blocks == 1

    async def test_duration_ms_passed_through(self) -> None:
        events = [{"type": "turn.completed", "usage": None}]
        turn = CodexTurn(_aiter(events), model="o4-mini", duration_ms=999)
        await _collect(turn)
        assert turn.usage().duration_ms == 999

    async def test_cost_usd_passed_through(self) -> None:
        events = [{"type": "turn.completed", "usage": None}]
        turn = CodexTurn(_aiter(events), model="o4-mini", cost_usd=0.007)
        await _collect(turn)
        assert turn.usage().cost_usd == pytest.approx(0.007)

    async def test_empty_stream_usage_still_valid(self) -> None:
        turn = CodexTurn(_aiter([]), model="o4-mini")
        await _collect(turn)
        u = turn.usage()
        assert isinstance(u, TurnUsage)
        assert u.num_llm_calls == 1

    async def test_reasoning_tokens_propagated(self) -> None:
        events = [
            {
                "type": "turn.completed",
                "usage": {
                    "input_tokens": 100,
                    "output_tokens": 60,
                    "reasoning_tokens": 40,
                    "total_tokens": 200,
                },
            }
        ]
        turn = CodexTurn(_aiter(events), model="o4-mini")
        await _collect(turn)
        assert turn.usage().reasoning_tokens == 40
