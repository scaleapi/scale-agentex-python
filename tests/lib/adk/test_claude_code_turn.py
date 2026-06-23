"""Tests for ClaudeCodeTurn and claude_code_usage_to_turn_usage."""

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
from agentex.types.tool_response_content import ToolResponseContent
from agentex.lib.adk._modules._claude_code_turn import (
    ClaudeCodeTurn,
    claude_code_usage_to_turn_usage,
)


async def _aiter(events: list[Any]) -> AsyncIterator[Any]:
    for e in events:
        yield e


async def _drain(turn: ClaudeCodeTurn) -> list[Any]:
    return [e async for e in turn.events]


# ---------------------------------------------------------------------------
# Usage normalization
# ---------------------------------------------------------------------------


class TestClaudeCodeUsageToTurnUsage:
    def test_full_usage_fields(self):
        result = {
            "usage": {
                "input_tokens": 100,
                "output_tokens": 50,
                "cache_read_input_tokens": 20,
                "cache_creation_input_tokens": 5,
            },
            "cost_usd": 0.025,
            "duration_ms": 3200,
            "num_turns": 3,
        }
        usage = claude_code_usage_to_turn_usage(result)

        assert usage.input_tokens == 100
        assert usage.output_tokens == 50
        assert usage.cached_input_tokens == 25  # 20 + 5
        assert usage.total_tokens == 150
        assert usage.cost_usd == pytest.approx(0.025)
        assert usage.duration_ms == 3200
        assert usage.num_llm_calls == 3

    def test_total_cost_usd_fallback(self):
        """total_cost_usd should be used when cost_usd is absent."""
        result = {
            "usage": {"input_tokens": 10, "output_tokens": 5},
            "total_cost_usd": 0.001,
        }
        usage = claude_code_usage_to_turn_usage(result)
        assert usage.cost_usd == pytest.approx(0.001)

    def test_cost_usd_takes_precedence_over_total_cost_usd(self):
        result = {
            "usage": {"input_tokens": 10, "output_tokens": 5},
            "cost_usd": 0.002,
            "total_cost_usd": 0.999,
        }
        usage = claude_code_usage_to_turn_usage(result)
        assert usage.cost_usd == pytest.approx(0.002)

    def test_missing_usage_key_returns_nones(self):
        result: dict[str, Any] = {}
        usage = claude_code_usage_to_turn_usage(result)
        assert usage.input_tokens is None
        assert usage.output_tokens is None
        assert usage.cached_input_tokens is None
        assert usage.total_tokens is None
        assert usage.cost_usd is None
        assert usage.duration_ms is None
        assert usage.num_llm_calls is None

    def test_real_zeros_preserved(self):
        result = {
            "usage": {
                "input_tokens": 0,
                "output_tokens": 0,
                "cache_read_input_tokens": 0,
                "cache_creation_input_tokens": 0,
            },
            "cost_usd": 0.0,
            "duration_ms": 0,
            "num_turns": 0,
        }
        usage = claude_code_usage_to_turn_usage(result)
        assert usage.input_tokens == 0
        assert usage.output_tokens == 0
        assert usage.cached_input_tokens == 0
        assert usage.total_tokens == 0
        assert usage.cost_usd == pytest.approx(0.0)
        assert usage.duration_ms == 0
        assert usage.num_llm_calls == 0

    def test_only_cache_read_no_creation(self):
        result = {
            "usage": {
                "input_tokens": 50,
                "output_tokens": 25,
                "cache_read_input_tokens": 15,
            }
        }
        usage = claude_code_usage_to_turn_usage(result)
        assert usage.cached_input_tokens == 15

    def test_only_cache_creation_no_read(self):
        result = {
            "usage": {
                "input_tokens": 50,
                "output_tokens": 25,
                "cache_creation_input_tokens": 10,
            }
        }
        usage = claude_code_usage_to_turn_usage(result)
        assert usage.cached_input_tokens == 10

    def test_no_cache_fields_gives_none(self):
        result = {"usage": {"input_tokens": 10, "output_tokens": 5}}
        usage = claude_code_usage_to_turn_usage(result)
        assert usage.cached_input_tokens is None

    def test_total_tokens_computed_from_input_output(self):
        result = {"usage": {"input_tokens": 70, "output_tokens": 30}}
        usage = claude_code_usage_to_turn_usage(result)
        assert usage.total_tokens == 100

    def test_missing_output_tokens_leaves_total_none(self):
        result = {"usage": {"input_tokens": 70}}
        usage = claude_code_usage_to_turn_usage(result)
        assert usage.total_tokens is None

    def test_returns_turn_usage_instance(self):
        result = {"usage": {"input_tokens": 1, "output_tokens": 1}}
        usage = claude_code_usage_to_turn_usage(result)
        assert isinstance(usage, TurnUsage)


# ---------------------------------------------------------------------------
# ClaudeCodeTurn protocol
# ---------------------------------------------------------------------------


class TestClaudeCodeTurnProtocol:
    def test_satisfies_harness_turn_protocol(self):
        """ClaudeCodeTurn must satisfy the HarnessTurn structural protocol."""
        turn = ClaudeCodeTurn(_aiter([]))
        assert isinstance(turn, HarnessTurn)

    async def test_events_yields_stream_task_messages(self):
        envelopes = [
            {
                "type": "assistant",
                "message": {"content": [{"type": "text", "text": "Hi there"}]},
            }
        ]
        turn = ClaudeCodeTurn(_aiter(envelopes))
        out = await _drain(turn)
        assert len(out) == 3
        assert isinstance(out[0], StreamTaskMessageStart)
        assert isinstance(out[1], StreamTaskMessageDelta)
        assert isinstance(out[2], StreamTaskMessageDone)

    async def test_usage_before_drain_returns_empty(self):
        envelopes = [
            {
                "type": "result",
                "usage": {"input_tokens": 100, "output_tokens": 50},
                "cost_usd": 0.01,
            }
        ]
        turn = ClaudeCodeTurn(_aiter(envelopes))
        # usage() called before events drained — no result envelope yet
        usage = turn.usage()
        assert isinstance(usage, TurnUsage)
        assert usage.input_tokens is None

    async def test_usage_after_drain_reflects_result(self):
        envelopes = [
            {
                "type": "assistant",
                "message": {"content": [{"type": "text", "text": "response"}]},
            },
            {
                "type": "result",
                "usage": {"input_tokens": 200, "output_tokens": 80},
                "cost_usd": 0.015,
                "num_turns": 2,
            },
        ]
        turn = ClaudeCodeTurn(_aiter(envelopes))
        await _drain(turn)
        usage = turn.usage()

        assert usage.input_tokens == 200
        assert usage.output_tokens == 80
        assert usage.cost_usd == pytest.approx(0.015)
        assert usage.num_llm_calls == 2

    async def test_usage_empty_when_no_result_envelope(self):
        envelopes = [
            {
                "type": "assistant",
                "message": {"content": [{"type": "text", "text": "no result"}]},
            }
        ]
        turn = ClaudeCodeTurn(_aiter(envelopes))
        await _drain(turn)
        usage = turn.usage()
        assert usage.input_tokens is None
        assert usage.cost_usd is None

    async def test_tool_call_and_result_round_trip(self):
        envelopes = [
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "call_1",
                            "name": "Read",
                            "input": {"path": "/etc/hosts"},
                        }
                    ]
                },
            },
            {
                "type": "user",
                "message": {
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "call_1",
                            "content": "127.0.0.1 localhost",
                        }
                    ]
                },
            },
            {
                "type": "result",
                "usage": {"input_tokens": 50, "output_tokens": 20},
                "cost_usd": 0.005,
            },
        ]
        turn = ClaudeCodeTurn(_aiter(envelopes))
        out = await _drain(turn)
        usage = turn.usage()

        tool_starts = [
            e for e in out if isinstance(e, StreamTaskMessageStart) and isinstance(e.content, ToolResponseContent)
        ]
        tool_fulls = [
            e for e in out if isinstance(e, StreamTaskMessageFull) and isinstance(e.content, ToolResponseContent)
        ]
        assert len(tool_fulls) == 1
        full_content = tool_fulls[0].content
        assert isinstance(full_content, ToolResponseContent)
        assert full_content.tool_call_id == "call_1"

        assert usage.input_tokens == 50
        assert usage.output_tokens == 20

    async def test_events_property_returns_same_iterator(self):
        """Accessing .events multiple times returns the same iterator (not a new one each call)."""
        turn = ClaudeCodeTurn(_aiter([]))
        it1 = turn.events
        it2 = turn.events
        assert it1 is it2
