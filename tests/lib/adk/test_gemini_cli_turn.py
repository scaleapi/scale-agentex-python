"""Tests for GeminiCliTurn and gemini_cli_usage_to_turn_usage."""

from __future__ import annotations

from typing import Any, AsyncIterator

from agentex.lib.core.harness.types import TurnUsage, HarnessTurn
from agentex.types.task_message_update import StreamTaskMessageDone, StreamTaskMessageStart
from agentex.lib.adk._modules._gemini_cli_turn import (
    GeminiCliTurn,
    gemini_cli_usage_to_turn_usage,
)


async def _aiter(events: list[Any]) -> AsyncIterator[Any]:
    for e in events:
        yield e


def _result(stats: dict[str, Any] | None) -> dict[str, Any]:
    evt: dict[str, Any] = {"type": "result", "status": "success"}
    if stats is not None:
        evt["stats"] = stats
    return evt


class TestGeminiCliUsageToTurnUsage:
    def test_full_stats(self):
        usage = gemini_cli_usage_to_turn_usage(
            _result(
                {
                    "total_tokens": 30,
                    "input_tokens": 20,
                    "output_tokens": 10,
                    "cached": 5,
                    "input": 15,
                    "duration_ms": 1234,
                    "tool_calls": 2,
                    "models": {"gemini-2.5-flash": {}},
                }
            )
        )
        assert usage.input_tokens == 20
        assert usage.output_tokens == 10
        assert usage.cached_input_tokens == 5
        assert usage.total_tokens == 30
        assert usage.duration_ms == 1234
        assert usage.num_tool_calls == 2
        assert usage.model == "gemini-2.5-flash"
        assert usage.cost_usd is None
        assert usage.num_llm_calls is None

    def test_explicit_model_wins_over_stats(self):
        usage = gemini_cli_usage_to_turn_usage(_result({"models": {"from-stats": {}}}), model="from-init")
        assert usage.model == "from-init"

    def test_missing_stats_returns_nones(self):
        usage = gemini_cli_usage_to_turn_usage(_result(None))
        assert usage.input_tokens is None and usage.output_tokens is None and usage.total_tokens is None
        assert usage.duration_ms is None and usage.num_tool_calls == 0 and usage.model is None

    def test_total_computed_when_absent(self):
        usage = gemini_cli_usage_to_turn_usage(_result({"input_tokens": 2, "output_tokens": 3}))
        assert usage.total_tokens == 5

    def test_real_zeros_preserved(self):
        usage = gemini_cli_usage_to_turn_usage(
            _result({"input_tokens": 0, "output_tokens": 0, "cached": 0, "tool_calls": 0})
        )
        assert usage.input_tokens == 0 and usage.cached_input_tokens == 0 and usage.total_tokens == 0

    def test_returns_turn_usage_instance(self):
        assert isinstance(gemini_cli_usage_to_turn_usage(_result({})), TurnUsage)


class TestGeminiCliTurnProtocol:
    def test_satisfies_harness_turn_protocol(self):
        turn = GeminiCliTurn(_aiter([]))
        assert isinstance(turn, HarnessTurn)

    async def test_events_yields_stream_task_messages(self):
        turn = GeminiCliTurn(
            _aiter([{"type": "message", "role": "assistant", "content": "hi", "delta": True}, _result({})])
        )
        events = [e async for e in turn.events]
        assert isinstance(events[0], StreamTaskMessageStart)
        assert isinstance(events[-1], StreamTaskMessageDone)

    async def test_usage_before_drain_is_empty(self):
        turn = GeminiCliTurn(_aiter([_result({"input_tokens": 1})]))
        assert turn.usage() == TurnUsage()

    async def test_usage_after_drain_reflects_result_and_init_model(self):
        turn = GeminiCliTurn(
            _aiter(
                [
                    {"type": "init", "session_id": "s-9", "model": "gemini-2.5-pro"},
                    _result({"input_tokens": 7, "output_tokens": 1}),
                ]
            )
        )
        _ = [e async for e in turn.events]
        usage = turn.usage()
        assert usage.input_tokens == 7 and usage.total_tokens == 8 and usage.model == "gemini-2.5-pro"
        assert turn.session_id == "s-9" and turn.model == "gemini-2.5-pro"

    async def test_usage_empty_when_no_result_event(self):
        turn = GeminiCliTurn(
            _aiter(
                [
                    {"type": "init", "model": "m"},
                    {"type": "message", "role": "assistant", "content": "x", "delta": True},
                ]
            )
        )
        _ = [e async for e in turn.events]
        assert turn.usage() == TurnUsage(model="m")

    async def test_events_property_returns_same_iterator(self):
        turn = GeminiCliTurn(_aiter([]))
        assert turn.events is turn.events
