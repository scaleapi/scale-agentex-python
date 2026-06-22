"""Tests for OpenAITurn and its usage mapping.

OpenAITurn adapts an OpenAI Agents SDK streamed run onto the harness
``HarnessTurn`` protocol. These tests cover:
- ``openai_usage_to_turn_usage`` (full usage, None, real zeros)
- ``_aggregate_usage`` (empty, single, multiple ModelResponses)
- ``OpenAITurn.events`` driven by an injected canonical stream (bypassing the
  OpenAI->canonical converter), plus ``usage()`` before/after exhaustion
- the ``ValueError`` guard when neither ``result`` nor ``stream`` is supplied
"""

import types as _types

import pytest
from agents.usage import Usage
from openai.types.responses.response_usage import InputTokensDetails, OutputTokensDetails

from agentex.types.text_content import TextContent
from agentex.types.task_message_delta import TextDelta
from agentex.types.task_message_update import (
    StreamTaskMessageDone,
    StreamTaskMessageDelta,
    StreamTaskMessageStart,
)


def _import_target():
    from agentex.lib.adk.providers._modules.openai_turn import (
        OpenAITurn,
        _aggregate_usage,
        openai_usage_to_turn_usage,
    )

    return OpenAITurn, _aggregate_usage, openai_usage_to_turn_usage


# ---------------------------------------------------------------------------
# openai_usage_to_turn_usage
# ---------------------------------------------------------------------------


def test_usage_mapping_full():
    _, _, openai_usage_to_turn_usage = _import_target()
    usage = Usage(
        requests=3,
        input_tokens=100,
        input_tokens_details=InputTokensDetails(cached_tokens=20),
        output_tokens=50,
        output_tokens_details=OutputTokensDetails(reasoning_tokens=10),
        total_tokens=150,
    )
    turn_usage = openai_usage_to_turn_usage(usage, model="gpt-4o")

    assert turn_usage.model == "gpt-4o"
    assert turn_usage.num_llm_calls == 3
    assert turn_usage.input_tokens == 100
    assert turn_usage.cached_input_tokens == 20
    assert turn_usage.output_tokens == 50
    assert turn_usage.reasoning_tokens == 10
    assert turn_usage.total_tokens == 150


def test_usage_mapping_none_usage():
    _, _, openai_usage_to_turn_usage = _import_target()
    turn_usage = openai_usage_to_turn_usage(None, model="gpt-4o")

    assert turn_usage.model == "gpt-4o"
    # num_llm_calls is None ("not reported") when no usage is present, matching
    # the token fields below; a real 0 is only reported when the provider says so.
    assert turn_usage.num_llm_calls is None
    assert turn_usage.input_tokens is None
    assert turn_usage.output_tokens is None
    assert turn_usage.total_tokens is None


def test_usage_mapping_real_zeros_are_preserved():
    # A cache hit can legitimately produce 0 output tokens; a present-but-zero
    # value must survive as 0, not be coerced to None.
    _, _, openai_usage_to_turn_usage = _import_target()
    usage = Usage(
        requests=1,
        input_tokens=0,
        input_tokens_details=InputTokensDetails(cached_tokens=0),
        output_tokens=0,
        output_tokens_details=OutputTokensDetails(reasoning_tokens=0),
        total_tokens=0,
    )
    turn_usage = openai_usage_to_turn_usage(usage, model="m")

    assert turn_usage.input_tokens == 0
    assert turn_usage.cached_input_tokens == 0
    assert turn_usage.output_tokens == 0
    assert turn_usage.reasoning_tokens == 0
    assert turn_usage.total_tokens == 0
    assert turn_usage.num_llm_calls == 1


# ---------------------------------------------------------------------------
# _aggregate_usage
# ---------------------------------------------------------------------------


def _resp(usage):
    return _types.SimpleNamespace(usage=usage)


def test_aggregate_usage_empty():
    _, _aggregate_usage, _ = _import_target()
    assert _aggregate_usage([]) is None


def test_aggregate_usage_single():
    _, _aggregate_usage, _ = _import_target()
    usage = Usage(requests=1, input_tokens=10, output_tokens=5, total_tokens=15)
    total = _aggregate_usage([_resp(usage)])

    assert total is not None
    assert total.requests == 1
    assert total.input_tokens == 10
    assert total.output_tokens == 5
    assert total.total_tokens == 15


def test_aggregate_usage_multiple():
    _, _aggregate_usage, _ = _import_target()
    u1 = Usage(
        requests=1,
        input_tokens=10,
        input_tokens_details=InputTokensDetails(cached_tokens=2),
        output_tokens=5,
        output_tokens_details=OutputTokensDetails(reasoning_tokens=1),
        total_tokens=15,
    )
    u2 = Usage(
        requests=2,
        input_tokens=20,
        input_tokens_details=InputTokensDetails(cached_tokens=3),
        output_tokens=7,
        output_tokens_details=OutputTokensDetails(reasoning_tokens=4),
        total_tokens=27,
    )
    # A response without usage must be skipped, not crash the aggregation.
    total = _aggregate_usage([_resp(u1), _resp(None), _resp(u2)])

    assert total is not None
    assert total.requests == 3
    assert total.input_tokens == 30
    assert total.output_tokens == 12
    assert total.total_tokens == 42
    assert total.input_tokens_details.cached_tokens == 5
    assert total.output_tokens_details.reasoning_tokens == 5


# ---------------------------------------------------------------------------
# OpenAITurn.events / usage / construction
# ---------------------------------------------------------------------------


async def _canonical_stream(events):
    for e in events:
        yield e


@pytest.mark.asyncio
async def test_turn_events_forwards_injected_stream():
    OpenAITurn, _, _ = _import_target()
    events = [
        StreamTaskMessageStart(type="start", index=0, content=TextContent(type="text", author="agent", content="")),
        StreamTaskMessageDelta(type="delta", index=0, delta=TextDelta(type="text", text_delta="Hi")),
        StreamTaskMessageDone(type="done", index=0),
    ]
    turn = OpenAITurn(stream=_canonical_stream(events), model="gpt-4o")

    out = [e async for e in turn.events]
    assert out == events


@pytest.mark.asyncio
async def test_turn_usage_before_and_after_exhaustion_with_injected_stream():
    OpenAITurn, _, _ = _import_target()
    events = [
        StreamTaskMessageStart(type="start", index=0, content=TextContent(type="text", author="agent", content="")),
        StreamTaskMessageDone(type="done", index=0),
    ]
    turn = OpenAITurn(stream=_canonical_stream(events), model="gpt-4o")

    # Before exhaustion: usage carries only the model name.
    before = turn.usage()
    assert before.model == "gpt-4o"
    assert before.input_tokens is None

    async for _ in turn.events:
        pass

    # With an injected stream there is no run to read usage from, so usage
    # stays model-only after exhaustion.
    after = turn.usage()
    assert after.model == "gpt-4o"
    assert after.input_tokens is None


@pytest.mark.asyncio
async def test_turn_usage_populated_from_result_after_exhaustion():
    OpenAITurn, _, _ = _import_target()

    canonical = [
        StreamTaskMessageStart(type="start", index=0, content=TextContent(type="text", author="agent", content="")),
        StreamTaskMessageDone(type="done", index=0),
    ]

    class _FakeResult:
        def __init__(self):
            self.raw_responses = [
                _resp(Usage(requests=1, input_tokens=8, output_tokens=4, total_tokens=12)),
            ]

        def stream_events(self):
            # OpenAITurn passes this to convert_openai_to_agentex_events; we
            # monkeypatch that converter below so this can yield canonical events.
            return _canonical_stream(canonical)

    import agentex.lib.adk.providers._modules.openai_turn as mod

    async def _passthrough(stream):
        async for e in stream:
            yield e

    original = mod.convert_openai_to_agentex_events
    mod.convert_openai_to_agentex_events = _passthrough
    try:
        turn = OpenAITurn(result=_FakeResult(), model="gpt-4o")
        out = [e async for e in turn.events]
    finally:
        mod.convert_openai_to_agentex_events = original

    assert out == canonical
    usage = turn.usage()
    assert usage.model == "gpt-4o"
    assert usage.num_llm_calls == 1
    assert usage.input_tokens == 8
    assert usage.output_tokens == 4
    assert usage.total_tokens == 12


def test_turn_requires_result_or_stream():
    OpenAITurn, _, _ = _import_target()
    with pytest.raises(ValueError, match="either"):
        OpenAITurn()
