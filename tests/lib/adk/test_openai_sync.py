"""Tests for ``convert_openai_to_agentex_events`` and its helpers.

Focused on three previously-broken behaviors on the sync OpenAI converter:

- ``_safe_parse_arguments`` never raises on malformed/non-dict JSON (a bad
  tool-args string must not abort the whole turn).
- Every streamed item — text AND reasoning — is closed with a matching
  ``StreamTaskMessageDone`` (reasoning messages used to hang open).
- Each new text ``item_id`` gets a fresh index, so a final answer cannot
  collide with the preceding reasoning message on reasoning-model streams.
"""

import types as _types

import pytest
from openai.types.responses import ResponseTextDeltaEvent, ResponseOutputItemDoneEvent
from openai.types.responses.response_output_message import ResponseOutputMessage
from openai.types.responses.response_reasoning_item import ResponseReasoningItem
from openai.types.responses.response_reasoning_text_delta_event import ResponseReasoningTextDeltaEvent

from agentex.types.task_message_update import (
    StreamTaskMessageDone,
    StreamTaskMessageDelta,
    StreamTaskMessageStart,
)
from agentex.lib.adk._modules._openai_sync import (
    _safe_parse_arguments,
    convert_openai_to_agentex_events,
)

# ---------------------------------------------------------------------------
# _safe_parse_arguments
# ---------------------------------------------------------------------------


def test_safe_parse_arguments_valid_dict_json():
    assert _safe_parse_arguments('{"a": 1}') == {"a": 1}


def test_safe_parse_arguments_empty_and_none():
    assert _safe_parse_arguments("") == {}
    assert _safe_parse_arguments(None) == {}


def test_safe_parse_arguments_passthrough_dict():
    d = {"already": "dict"}
    assert _safe_parse_arguments(d) is d


def test_safe_parse_arguments_malformed_preserved_not_raised():
    # A truncated / malformed payload must be preserved, never raise — raising
    # here would abort the whole turn before later output is delivered.
    assert _safe_parse_arguments('{"a": ') == {"raw": '{"a": '}


def test_safe_parse_arguments_non_dict_json_wrapped():
    # Valid JSON that isn't an object is wrapped so the result stays a dict.
    assert _safe_parse_arguments("[1, 2]") == {"value": [1, 2]}
    assert _safe_parse_arguments("42") == {"value": 42}


# ---------------------------------------------------------------------------
# convert_openai_to_agentex_events — reasoning + text sequencing
# ---------------------------------------------------------------------------


def _raw(data):
    return _types.SimpleNamespace(type="raw_response_event", data=data)


async def _stream(events):
    for e in events:
        yield e


async def _collect(events):
    return [e async for e in convert_openai_to_agentex_events(_stream(events))]


@pytest.mark.asyncio
async def test_reasoning_item_emits_done():
    """A completed reasoning item must yield a matching Done (it used to be skipped)."""
    events = [
        _raw(
            ResponseReasoningTextDeltaEvent(
                type="response.reasoning_text.delta",
                item_id="r1",
                content_index=0,
                delta="thinking",
                output_index=0,
                sequence_number=1,
            )
        ),
        _raw(
            ResponseOutputItemDoneEvent(
                type="response.output_item.done",
                item=ResponseReasoningItem(id="r1", type="reasoning", summary=[]),
                output_index=0,
                sequence_number=2,
            )
        ),
    ]
    out = await _collect(events)

    starts = [e for e in out if isinstance(e, StreamTaskMessageStart)]
    dones = [e for e in out if isinstance(e, StreamTaskMessageDone)]
    assert len(starts) == 1
    # The reasoning message is now closed instead of hanging open.
    assert [d.index for d in dones] == [starts[0].index]


@pytest.mark.asyncio
async def test_reasoning_then_text_use_distinct_indices():
    """Final answer text must not reuse the reasoning message's index."""
    events = [
        _raw(
            ResponseReasoningTextDeltaEvent(
                type="response.reasoning_text.delta",
                item_id="r1",
                content_index=0,
                delta="thinking",
                output_index=0,
                sequence_number=1,
            )
        ),
        _raw(
            ResponseOutputItemDoneEvent(
                type="response.output_item.done",
                item=ResponseReasoningItem(id="r1", type="reasoning", summary=[]),
                output_index=0,
                sequence_number=2,
            )
        ),
        _raw(
            ResponseTextDeltaEvent(
                type="response.output_text.delta",
                item_id="t1",
                content_index=0,
                delta="answer",
                output_index=1,
                sequence_number=3,
                logprobs=[],
            )
        ),
        _raw(
            ResponseOutputItemDoneEvent(
                type="response.output_item.done",
                item=ResponseOutputMessage(id="t1", type="message", role="assistant", status="completed", content=[]),
                output_index=1,
                sequence_number=4,
            )
        ),
    ]
    out = await _collect(events)

    starts = [e for e in out if isinstance(e, StreamTaskMessageStart)]
    assert len(starts) == 2
    reasoning_index, text_index = starts[0].index, starts[1].index
    assert reasoning_index != text_index

    # Text deltas route to the text index, not the reasoning index.
    text_deltas = [e for e in out if isinstance(e, StreamTaskMessageDelta) and e.delta.type == "text"]
    assert text_deltas and all(d.index == text_index for d in text_deltas)

    # Both messages are closed on their own index.
    done_indices = sorted(e.index for e in out if isinstance(e, StreamTaskMessageDone))
    assert done_indices == sorted({reasoning_index, text_index})
