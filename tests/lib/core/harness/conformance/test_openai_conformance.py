"""OpenAI conformance fixtures for the shared harness span-derivation engine.

The cross-channel guarantee is that yield-delivery and auto_send observe the
SAME canonical StreamTaskMessage* stream, so span derivation and logical
delivery over that stream must be equivalent regardless of channel. These
fixtures express the canonical sequences an OpenAI turn produces (text,
tool-call, reasoning, and a combined multi-step turn) and assert that property
via run_cross_channel_conformance.

Registry hazard (see conformance/runner.py): _REGISTRY is process-global and
collection order across modules is not guaranteed. To stay deterministic this
module keeps its OWN fixture list and parametrizes over THAT list, rather than
over all_fixtures(). It still calls register() so the cross-module conformance
suite can see these fixtures too.
"""

from __future__ import annotations

import pytest

from agentex.types.text_delta import TextDelta
from agentex.types.text_content import TextContent
from agentex.types.reasoning_content import ReasoningContent
from agentex.types.task_message_update import (
    StreamTaskMessageDone,
    StreamTaskMessageFull,
    StreamTaskMessageDelta,
    StreamTaskMessageStart,
)
from agentex.types.tool_request_content import ToolRequestContent
from agentex.types.tool_response_content import ToolResponseContent
from agentex.types.reasoning_content_delta import ReasoningContentDelta

from .runner import Fixture, register, run_cross_channel_conformance

_OPENAI_FIXTURES: list[Fixture] = []


def _add(fixture: Fixture) -> None:
    """Register both module-locally (for parametrization) and globally."""
    _OPENAI_FIXTURES.append(fixture)
    register(fixture)


# Text-only turn: start -> deltas -> done.
# Uses non-empty initial_content so payload comparison catches a channel that
# drops StreamTaskMessageStart.content.
_add(
    Fixture(
        name="openai-text-only",
        events=[
            StreamTaskMessageStart(
                type="start",
                index=0,
                content=TextContent(type="text", author="agent", content="Init"),
            ),
            StreamTaskMessageDelta(type="delta", index=0, delta=TextDelta(type="text", text_delta="Hel")),
            StreamTaskMessageDelta(type="delta", index=0, delta=TextDelta(type="text", text_delta="lo")),
            StreamTaskMessageDone(type="done", index=0),
        ],
    )
)

# Tool-call turn: Full(ToolRequestContent) for the call + Full(ToolResponseContent)
# for the result, matched by tool_call_id. Mirrors the OpenAI converter's tool path.
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

# Reasoning turn: start(ReasoningContent) -> content deltas -> done.
# ReasoningContent.summary is seeded in the payload so a channel that drops the
# summary fails the cross-channel comparison.
_add(
    Fixture(
        name="openai-reasoning",
        events=[
            StreamTaskMessageStart(
                type="start",
                index=0,
                content=ReasoningContent(
                    type="reasoning",
                    author="agent",
                    summary=["Thinking..."],
                ),
            ),
            StreamTaskMessageDelta(
                type="delta",
                index=0,
                delta=ReasoningContentDelta(
                    type="reasoning_content",
                    content_index=0,
                    content_delta="step 1",
                ),
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
                content=ReasoningContent(
                    type="reasoning",
                    author="agent",
                    summary=["plan"],
                ),
            ),
            StreamTaskMessageDelta(
                type="delta",
                index=0,
                delta=ReasoningContentDelta(
                    type="reasoning_content",
                    content_index=0,
                    content_delta="elaboration",
                ),
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
@pytest.mark.asyncio
async def test_openai_cross_channel_equivalence(fixture: Fixture) -> None:
    """Assert that yield_events and auto_send produce equivalent logical
    deliveries and identical span signals for every OpenAI fixture.

    This is the cross-channel guarantee: the two delivery adapters agree on
    WHAT was delivered (logical content) and HOW spans were derived, even
    though their streaming-envelope shapes differ (Full vs Start+Done for tool
    messages).

    The span signals are the ones each channel's tracer ACTUALLY recorded while
    delivering, not a re-derivation, so a regression where one channel skips
    deriver.observe() for some event type is caught here.
    """
    yield_deliveries, auto_deliveries, yield_spans, auto_spans = await run_cross_channel_conformance(fixture)

    assert yield_deliveries == auto_deliveries, (
        f"[{fixture.name}] logical deliveries differ:\n  yield:     {yield_deliveries}\n  auto_send: {auto_deliveries}"
    )
    assert yield_spans == auto_spans, (
        f"[{fixture.name}] span signals differ:\n  yield:     {yield_spans}\n  auto_send: {auto_spans}"
    )
