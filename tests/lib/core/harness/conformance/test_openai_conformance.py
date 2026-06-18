"""OpenAI conformance fixtures for the shared harness span-derivation engine.

The cross-channel guarantee is that yield-delivery and auto-send observe the
SAME canonical ``StreamTaskMessage*`` stream, so span derivation over that
stream must be deterministic and idempotent regardless of channel. These
fixtures express the canonical sequences an OpenAI turn produces (text,
tool-call, reasoning, and a combined multi-step turn) and assert that property.

Registry hazard (see conformance/runner.py): ``_REGISTRY`` is process-global and
collection order across modules is not guaranteed. To stay deterministic this
module keeps its OWN fixture list and parametrizes over THAT list, rather than
over ``all_fixtures()``. It still calls ``register()`` so the cross-module
conformance suite can see these fixtures too.
"""

from __future__ import annotations

import pytest

from agentex.types.text_content import TextContent
from agentex.types.reasoning_content import ReasoningContent
from agentex.types.task_message_delta import TextDelta, ReasoningSummaryDelta
from agentex.types.task_message_update import (
    StreamTaskMessageDone,
    StreamTaskMessageFull,
    StreamTaskMessageDelta,
    StreamTaskMessageStart,
)
from agentex.types.tool_request_content import ToolRequestContent
from agentex.types.tool_response_content import ToolResponseContent

from .runner import Fixture, register, derive_all

_OPENAI_FIXTURES: list[Fixture] = []


def _add(fixture: Fixture) -> None:
    """Register both module-locally (for parametrization) and globally."""
    _OPENAI_FIXTURES.append(fixture)
    register(fixture)


# Text-only turn: start -> deltas -> done. No spans are derived from plain text.
_add(
    Fixture(
        name="openai-text-only",
        events=[
            StreamTaskMessageStart(
                type="start",
                index=0,
                content=TextContent(type="text", author="agent", content=""),
            ),
            StreamTaskMessageDelta(type="delta", index=0, delta=TextDelta(type="text", text_delta="Hel")),
            StreamTaskMessageDelta(type="delta", index=0, delta=TextDelta(type="text", text_delta="lo")),
            StreamTaskMessageDone(type="done", index=0),
        ],
    )
)

# Tool-call turn: the OpenAI converter emits a single Full(ToolRequestContent)
# for the call and a Full(ToolResponseContent) for the result, matched by
# tool_call_id. Mirrors convert_openai_to_agentex_events' tool path.
_add(
    Fixture(
        name="openai-tool-call",
        events=[
            StreamTaskMessageFull(
                type="full",
                index=0,
                content=ToolRequestContent(
                    type="tool_request",
                    author="agent",
                    tool_call_id="call_1",
                    name="get_weather",
                    arguments={"city": "SF"},
                ),
            ),
            StreamTaskMessageFull(
                type="full",
                index=1,
                content=ToolResponseContent(
                    type="tool_response",
                    author="agent",
                    tool_call_id="call_1",
                    name="get_weather",
                    content="72F",
                ),
            ),
        ],
    )
)

# Reasoning turn: start(ReasoningContent) -> summary deltas -> done. Span
# derivation opens a reasoning span on Start and closes it on the index's Done.
_add(
    Fixture(
        name="openai-reasoning",
        events=[
            StreamTaskMessageStart(
                type="start",
                index=0,
                content=ReasoningContent(type="reasoning", author="agent", summary=[], content=[], style="active"),
            ),
            StreamTaskMessageDelta(
                type="delta",
                index=0,
                delta=ReasoningSummaryDelta(type="reasoning_summary", summary_index=0, summary_delta="thinking"),
            ),
            StreamTaskMessageDone(type="done", index=0),
        ],
    )
)

# Multi-step turn: reasoning, then a tool round, then the final answer text.
_add(
    Fixture(
        name="openai-multi-step",
        events=[
            StreamTaskMessageStart(
                type="start",
                index=0,
                content=ReasoningContent(type="reasoning", author="agent", summary=[], content=[], style="active"),
            ),
            StreamTaskMessageDelta(
                type="delta",
                index=0,
                delta=ReasoningSummaryDelta(type="reasoning_summary", summary_index=0, summary_delta="plan"),
            ),
            StreamTaskMessageDone(type="done", index=0),
            StreamTaskMessageFull(
                type="full",
                index=1,
                content=ToolRequestContent(
                    type="tool_request",
                    author="agent",
                    tool_call_id="call_2",
                    name="search",
                    arguments={"q": "x"},
                ),
            ),
            StreamTaskMessageFull(
                type="full",
                index=2,
                content=ToolResponseContent(
                    type="tool_response",
                    author="agent",
                    tool_call_id="call_2",
                    name="search",
                    content="result",
                ),
            ),
            StreamTaskMessageStart(
                type="start",
                index=3,
                content=TextContent(type="text", author="agent", content=""),
            ),
            StreamTaskMessageDelta(type="delta", index=3, delta=TextDelta(type="text", text_delta="done")),
            StreamTaskMessageDone(type="done", index=3),
        ],
    )
)


@pytest.mark.parametrize("fixture", _OPENAI_FIXTURES, ids=lambda f: f.name)
def test_openai_span_derivation_is_deterministic(fixture):
    """Deriving twice over the same canonical events yields identical signals,
    which is exactly what makes yield-delivery and auto-send equivalent (both
    observe the same stream)."""
    assert derive_all(fixture.events) == derive_all(fixture.events)
