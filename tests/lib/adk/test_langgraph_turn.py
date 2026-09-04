"""Tests for LangGraphTurn and langgraph_usage_to_turn_usage."""

from __future__ import annotations

import sys
from typing import Any

import pytest

from agentex.lib.core.harness.types import TurnUsage
from agentex.lib.adk._modules._langgraph_turn import LangGraphTurn, langgraph_usage_to_turn_usage

# ---------------------------------------------------------------------------
# Remove conftest stubs so real langchain_core types are used
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _real_langchain_core():
    stub_keys = [k for k in sys.modules if k.startswith("langchain_core") or k.startswith("langgraph")]
    saved = {k: sys.modules.pop(k) for k in stub_keys}
    import importlib

    importlib.import_module("langchain_core.messages")
    yield
    sys.modules.update(saved)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_stream(events: list[tuple[str, Any]]):
    async def _gen():
        for e in events:
            yield e

    return _gen()


async def _drain(turn: LangGraphTurn) -> list[Any]:
    return [e async for e in turn.events]


# ---------------------------------------------------------------------------
# langgraph_usage_to_turn_usage
# ---------------------------------------------------------------------------


class TestLangGraphUsageToTurnUsage:
    def test_none_usage_returns_empty_turn_usage(self):
        result = langgraph_usage_to_turn_usage(None, model="gpt-4")
        assert result == TurnUsage(model="gpt-4")

    def test_basic_token_fields_mapped(self):
        usage = {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}
        result = langgraph_usage_to_turn_usage(usage, model="gpt-4")
        assert result.input_tokens == 10
        assert result.output_tokens == 5
        assert result.total_tokens == 15
        assert result.model == "gpt-4"

    def test_zero_output_tokens_preserved_not_coerced_to_none(self):
        """Real zero counts must be preserved as 0, not None."""
        usage = {"input_tokens": 10, "output_tokens": 0, "total_tokens": 10}
        result = langgraph_usage_to_turn_usage(usage, model=None)
        assert result.output_tokens == 0

    def test_cache_read_mapped_to_cached_input_tokens(self):
        usage = {
            "input_tokens": 20,
            "output_tokens": 5,
            "total_tokens": 25,
            "input_token_details": {"cache_read": 8},
        }
        result = langgraph_usage_to_turn_usage(usage, model=None)
        assert result.cached_input_tokens == 8

    def test_reasoning_mapped_to_reasoning_tokens(self):
        usage = {
            "input_tokens": 10,
            "output_tokens": 15,
            "total_tokens": 25,
            "output_token_details": {"reasoning": 6},
        }
        result = langgraph_usage_to_turn_usage(usage, model=None)
        assert result.reasoning_tokens == 6

    def test_missing_optional_fields_are_none(self):
        usage = {"input_tokens": 5, "output_tokens": 3, "total_tokens": 8}
        result = langgraph_usage_to_turn_usage(usage, model=None)
        assert result.cached_input_tokens is None
        assert result.reasoning_tokens is None

    def test_full_usage_object(self):
        usage = {
            "input_tokens": 100,
            "output_tokens": 50,
            "total_tokens": 150,
            "input_token_details": {"cache_read": 30},
            "output_token_details": {"reasoning": 20},
        }
        result = langgraph_usage_to_turn_usage(usage, model="claude-3-5-sonnet")
        assert result == TurnUsage(
            model="claude-3-5-sonnet",
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            cached_input_tokens=30,
            reasoning_tokens=20,
        )

    def test_model_none_is_preserved(self):
        result = langgraph_usage_to_turn_usage({"input_tokens": 1}, model=None)
        assert result.model is None

    def test_empty_input_token_details_does_not_crash(self):
        usage = {"input_tokens": 5, "input_token_details": {}}
        result = langgraph_usage_to_turn_usage(usage, model=None)
        assert result.cached_input_tokens is None

    def test_empty_output_token_details_does_not_crash(self):
        usage = {"output_tokens": 5, "output_token_details": {}}
        result = langgraph_usage_to_turn_usage(usage, model=None)
        assert result.reasoning_tokens is None


# ---------------------------------------------------------------------------
# LangGraphTurn
# ---------------------------------------------------------------------------


class TestLangGraphTurn:
    async def test_events_yields_from_sync_converter(self):
        from langchain_core.messages import AIMessage, AIMessageChunk

        chunk = AIMessageChunk(content="Hello!")
        ai_msg = AIMessage(content="Hello!")
        stream = _make_stream(
            [
                ("messages", (chunk, {})),
                ("updates", {"agent": {"messages": [ai_msg]}}),
            ]
        )
        turn = LangGraphTurn(stream)
        events = await _drain(turn)
        assert len(events) > 0

    async def test_usage_is_empty_before_stream_consumed(self):
        turn = LangGraphTurn(_make_stream([]))
        # usage() before events consumed should return a default TurnUsage
        usage = turn.usage()
        assert isinstance(usage, TurnUsage)

    async def test_usage_captured_from_ai_message(self):
        from langchain_core.messages import AIMessage

        usage_meta = {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}
        ai_msg = AIMessage(content="Hi!", usage_metadata=usage_meta)
        stream = _make_stream([("updates", {"agent": {"messages": [ai_msg]}})])
        turn = LangGraphTurn(stream, model="gpt-4")
        await _drain(turn)

        usage = turn.usage()
        assert usage.input_tokens == 10
        assert usage.output_tokens == 5
        assert usage.total_tokens == 15
        assert usage.model == "gpt-4"

    async def test_usage_accumulates_across_multiple_ai_messages(self):
        """A multi-step turn (>1 LLM call) sums usage instead of keeping only the last."""
        from langchain_core.messages import AIMessage

        first = AIMessage(
            content="thinking",
            usage_metadata={
                "input_tokens": 10,
                "output_tokens": 5,
                "total_tokens": 15,
                "input_token_details": {"cache_read": 2},
                "output_token_details": {"reasoning": 1},
            },
        )
        second = AIMessage(
            content="answer",
            usage_metadata={
                "input_tokens": 20,
                "output_tokens": 7,
                "total_tokens": 27,
                "input_token_details": {"cache_read": 3},
                "output_token_details": {"reasoning": 4},
            },
        )
        stream = _make_stream(
            [
                ("updates", {"agent": {"messages": [first]}}),
                ("updates", {"agent": {"messages": [second]}}),
            ]
        )
        turn = LangGraphTurn(stream, model="gpt-4")
        await _drain(turn)

        usage = turn.usage()
        assert usage.input_tokens == 30
        assert usage.output_tokens == 12
        assert usage.total_tokens == 42
        assert usage.cached_input_tokens == 5
        assert usage.reasoning_tokens == 5
        assert usage.model == "gpt-4"

    async def test_usage_not_updated_when_no_usage_metadata(self):
        from langchain_core.messages import AIMessage

        ai_msg = AIMessage(content="Hi!")
        stream = _make_stream([("updates", {"agent": {"messages": [ai_msg]}})])
        turn = LangGraphTurn(stream, model="gpt-4")
        await _drain(turn)

        usage = turn.usage()
        assert usage == TurnUsage(model="gpt-4")

    async def test_usage_captures_cache_read_and_reasoning(self):
        from langchain_core.messages import AIMessage

        usage_meta = {
            "input_tokens": 100,
            "output_tokens": 50,
            "total_tokens": 150,
            "input_token_details": {"cache_read": 30},
            "output_token_details": {"reasoning": 20},
        }
        ai_msg = AIMessage(content="Result", usage_metadata=usage_meta)
        stream = _make_stream([("updates", {"agent": {"messages": [ai_msg]}})])
        turn = LangGraphTurn(stream, model="claude-3-5-sonnet")
        await _drain(turn)

        usage = turn.usage()
        assert usage.cached_input_tokens == 30
        assert usage.reasoning_tokens == 20

    async def test_harness_turn_protocol_conformance(self):
        """LangGraphTurn satisfies the HarnessTurn Protocol."""
        from agentex.lib.core.harness.types import HarnessTurn

        turn = LangGraphTurn(_make_stream([]))
        assert isinstance(turn, HarnessTurn), "LangGraphTurn must satisfy HarnessTurn Protocol"

    async def test_empty_stream_yields_no_events(self):
        turn = LangGraphTurn(_make_stream([]))
        events = await _drain(turn)
        assert events == []

    async def test_model_none_default(self):
        turn = LangGraphTurn(_make_stream([]))
        assert turn.usage().model is None

    async def test_model_passed_through_to_usage(self):
        from langchain_core.messages import AIMessage

        ai_msg = AIMessage(content="ok", usage_metadata={"input_tokens": 1, "output_tokens": 0, "total_tokens": 1})
        stream = _make_stream([("updates", {"agent": {"messages": [ai_msg]}})])
        turn = LangGraphTurn(stream, model="my-model")
        await _drain(turn)
        assert turn.usage().model == "my-model"
