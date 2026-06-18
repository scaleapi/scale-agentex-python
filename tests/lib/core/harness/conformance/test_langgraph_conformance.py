"""LangGraph conformance fixtures for the cross-channel span-derivation test.

Registers 4 LangGraph event sequences as conformance fixtures:
- text-only: a plain text response (no tool calls)
- single-tool: one tool call + response
- reasoning: a reasoning block + text
- multi-step: two turns with tool calls

AGX1-377 note: LangGraph emits tool requests as ``StreamTaskMessageFull``
(from "updates" events), NOT Start+Delta+Done like pydantic-ai. The SpanDeriver
does not produce tool spans from Full events today; that gap is tracked in
AGX1-373. The fixtures here document the current behavior and will be updated
when AGX1-373 resolves.
"""

from __future__ import annotations

import pytest

from agentex.types.text_content import TextContent
from agentex.types.reasoning_content import ReasoningContent
from agentex.types.task_message_delta import TextDelta
from agentex.types.task_message_update import (
    StreamTaskMessageDone,
    StreamTaskMessageFull,
    StreamTaskMessageDelta,
    StreamTaskMessageStart,
)
from agentex.types.tool_request_content import ToolRequestContent
from agentex.types.tool_response_content import ToolResponseContent
from agentex.types.reasoning_content_delta import ReasoningContentDelta

from .runner import Fixture, register, derive_all

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_TEXT_ONLY = Fixture(
    name="langgraph-text-only",
    events=[
        StreamTaskMessageStart(
            type="start",
            index=0,
            content=TextContent(type="text", author="agent", content=""),
        ),
        StreamTaskMessageDelta(
            type="delta",
            index=0,
            delta=TextDelta(type="text", text_delta="Hello from LangGraph!"),
        ),
        StreamTaskMessageDone(type="done", index=0),
    ],
)

_SINGLE_TOOL = Fixture(
    name="langgraph-single-tool",
    events=[
        # LangGraph tool request is a Full event (AGX1-377)
        StreamTaskMessageFull(
            type="full",
            index=0,
            content=ToolRequestContent(
                type="tool_request",
                author="agent",
                tool_call_id="call_1",
                name="get_weather",
                arguments={"city": "Paris"},
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
                content="Sunny, 72F",
            ),
        ),
        StreamTaskMessageStart(
            type="start",
            index=2,
            content=TextContent(type="text", author="agent", content=""),
        ),
        StreamTaskMessageDelta(
            type="delta",
            index=2,
            delta=TextDelta(type="text", text_delta="The weather in Paris is sunny, 72F."),
        ),
        StreamTaskMessageDone(type="done", index=2),
    ],
)

_REASONING = Fixture(
    name="langgraph-reasoning",
    events=[
        StreamTaskMessageStart(
            type="start",
            index=0,
            content=ReasoningContent(
                type="reasoning",
                author="agent",
                summary=[],
                content=[],
                style="active",
            ),
        ),
        StreamTaskMessageDelta(
            type="delta",
            index=0,
            delta=ReasoningContentDelta(
                type="reasoning_content",
                content_index=0,
                content_delta="Thinking about this...",
            ),
        ),
        StreamTaskMessageDone(type="done", index=0),
        StreamTaskMessageStart(
            type="start",
            index=1,
            content=TextContent(type="text", author="agent", content=""),
        ),
        StreamTaskMessageDelta(
            type="delta",
            index=1,
            delta=TextDelta(type="text", text_delta="The answer is 42."),
        ),
        StreamTaskMessageDone(type="done", index=1),
    ],
)

_MULTI_STEP = Fixture(
    name="langgraph-multi-step",
    events=[
        # Turn 1: text + tool call
        StreamTaskMessageStart(
            type="start",
            index=0,
            content=TextContent(type="text", author="agent", content=""),
        ),
        StreamTaskMessageDelta(
            type="delta",
            index=0,
            delta=TextDelta(type="text", text_delta="Let me search for that."),
        ),
        StreamTaskMessageDone(type="done", index=0),
        # Tool request (Full — AGX1-377)
        StreamTaskMessageFull(
            type="full",
            index=1,
            content=ToolRequestContent(
                type="tool_request",
                author="agent",
                tool_call_id="call_2",
                name="search",
                arguments={"query": "langgraph"},
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
                content="LangGraph is a framework for...",
            ),
        ),
        # Turn 2: final text
        StreamTaskMessageStart(
            type="start",
            index=3,
            content=TextContent(type="text", author="agent", content=""),
        ),
        StreamTaskMessageDelta(
            type="delta",
            index=3,
            delta=TextDelta(type="text", text_delta="Based on my research, LangGraph is..."),
        ),
        StreamTaskMessageDone(type="done", index=3),
    ],
)

_LANGGRAPH_FIXTURES = [_TEXT_ONLY, _SINGLE_TOOL, _REASONING, _MULTI_STEP]

for _fixture in _LANGGRAPH_FIXTURES:
    register(_fixture)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fixture", _LANGGRAPH_FIXTURES, ids=lambda f: f.name)
def test_langgraph_span_derivation_is_deterministic(fixture: Fixture):
    """Exercises the cross-channel guarantee: yield and auto-send observe the
    same event stream, so span derivation must be deterministic/idempotent.

    Deriving twice over the same events yields identical signals (the property
    that makes yield vs auto-send equivalent, since both observe the same stream).
    """
    assert derive_all(fixture.events) == derive_all(fixture.events)
