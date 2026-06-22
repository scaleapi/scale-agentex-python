"""Cross-channel conformance fixtures for LangGraph harness tap.

Each fixture is built as a canonical sequence of ``StreamTaskMessage*`` events
that matches what ``convert_langgraph_to_agentex_events`` (via ``LangGraphTurn``)
emits for the given scenario.  The fixtures are registered with the shared
conformance runner and exercised by both the cross-channel equivalence test
(yield_events vs auto_send) and the backward-compatible span-derivation test.

LangGraph-specific note
-----------------------
LangGraph emits tool *requests* as ``StreamTaskMessageFull`` events (from the
"updates" stream), NOT as Start+Delta+Done like pydantic-ai.  ``auto_send``
handles Full events by opening a streaming context with the full content and
closing it immediately, so both channels deliver the same logical payload.
No ``coalesce_tool_requests`` option is needed.
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

from .runner import Fixture, register, derive_all, run_cross_channel_conformance

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
        # LangGraph tool request is a Full event (from "updates" stream)
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
        # Turn 1: streaming text
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
        # Tool request (Full — from "updates" stream)
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
        # Turn 2: final streaming text
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
# Cross-channel conformance: logical equivalence + span equivalence
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fixture", _LANGGRAPH_FIXTURES, ids=lambda f: f.name)
@pytest.mark.asyncio
async def test_cross_channel_equivalence(fixture: Fixture) -> None:
    """Assert that yield_events and auto_send produce equivalent logical
    deliveries and identical span signals for each LangGraph fixture.

    See runner.py for the full contract.  The key LangGraph difference: tool
    requests arrive as Full events rather than Start+Delta+Done, so auto_send
    handles them by opening a streaming context with the full content and
    closing it immediately — both channels produce the same LogicalDelivery.
    """
    yield_deliveries, auto_deliveries, yield_spans, auto_spans = await run_cross_channel_conformance(fixture)

    assert yield_deliveries == auto_deliveries, (
        f"[{fixture.name}] logical deliveries differ:\n  yield:     {yield_deliveries}\n  auto_send: {auto_deliveries}"
    )
    assert yield_spans == auto_spans, (
        f"[{fixture.name}] span signals differ:\n  yield:     {yield_spans}\n  auto_send: {auto_spans}"
    )


# ---------------------------------------------------------------------------
# Backward-compatible determinism guard
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fixture", _LANGGRAPH_FIXTURES, ids=lambda f: f.name)
def test_span_derivation_is_deterministic(fixture: Fixture) -> None:
    """Span derivation over the same event list is idempotent."""
    assert derive_all(fixture.events) == derive_all(fixture.events)
