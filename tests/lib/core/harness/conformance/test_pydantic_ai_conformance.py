"""Cross-channel conformance fixtures derived from real pydantic-ai event sequences.

Each fixture is built by running a pydantic_ai event stream through PydanticAITurn
and collecting the canonical StreamTaskMessage* output. These canonical event lists are
then registered with the conformance runner and exercised by the cross-channel test
(yield_events vs auto_send).

Streamed tool requests
----------------------
The pydantic-ai stream emits a tool REQUEST as Start + ToolRequestDelta + Done (not a
Full event). AGX1-377 has landed: both the conformance runner and auto_send now deliver
the Start+Delta+Done(tool_request) shape, so the cross-channel test asserts full
delivery-equivalence for streamed tool requests. The fixtures below retain the
ToolRequestDelta events as the streamed tool-request inputs.
"""

from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator

import pytest
from pydantic_ai.messages import (
    TextPart,
    PartEndEvent,
    ThinkingPart,
    ToolCallPart,
    TextPartDelta,
    PartDeltaEvent,
    PartStartEvent,
    ToolReturnPart,
    ThinkingPartDelta,
    ToolCallPartDelta,
    FunctionToolResultEvent,
)

from agentex.lib.adk._modules._pydantic_ai_turn import PydanticAITurn

from .runner import (
    Fixture,
    register,
    derive_all,
    run_cross_channel_conformance,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _aiter(events: list[Any]) -> AsyncIterator[Any]:
    for e in events:
        yield e


async def _canonical(pydantic_events: list[Any]) -> list[Any]:
    """Run pydantic_ai events through PydanticAITurn and collect the output.

    The output equals the bare convert_pydantic_ai_to_agentex_events output.
    """
    turn = PydanticAITurn(_aiter(pydantic_events), model=None)
    return [e async for e in turn.events]


def _build_fixtures() -> list[Fixture]:
    """Build all pydantic-ai conformance fixtures synchronously via asyncio.run."""

    # ------------------------------------------------------------------ #
    # 1. Text-only run: simple streaming text response.
    # ------------------------------------------------------------------ #
    text_only_pydantic = [
        PartStartEvent(index=0, part=TextPart(content="")),
        PartDeltaEvent(index=0, delta=TextPartDelta(content_delta="Hello, ")),
        PartDeltaEvent(index=0, delta=TextPartDelta(content_delta="world!")),
        PartEndEvent(index=0, part=TextPart(content="Hello, world!")),
    ]

    # ------------------------------------------------------------------ #
    # 2. Single tool call + tool response.
    # The canonical stream emits Start+ToolRequestDelta+Done for the request
    # and Full(ToolResponseContent) for the response. See AGX1-377 note above
    # for why the request delivery is not yet asserted cross-channel.
    # ------------------------------------------------------------------ #
    tool_call_pydantic = [
        PartStartEvent(
            index=0,
            part=ToolCallPart(tool_name="get_weather", args=None, tool_call_id="call_01"),
        ),
        PartDeltaEvent(
            index=0,
            delta=ToolCallPartDelta(args_delta='{"city":"Paris"}', tool_call_id="call_01"),
        ),
        PartEndEvent(
            index=0,
            part=ToolCallPart(tool_name="get_weather", args='{"city":"Paris"}', tool_call_id="call_01"),
        ),
        FunctionToolResultEvent(
            part=ToolReturnPart(tool_name="get_weather", content="Sunny, 22C", tool_call_id="call_01"),
        ),
    ]

    # ------------------------------------------------------------------ #
    # 3. Reasoning/thinking block: produces ReasoningContent Start+Delta+Done.
    # ------------------------------------------------------------------ #
    reasoning_pydantic = [
        PartStartEvent(index=0, part=ThinkingPart(content="")),
        PartDeltaEvent(index=0, delta=ThinkingPartDelta(content_delta="First, let me think...")),
        PartDeltaEvent(index=0, delta=ThinkingPartDelta(content_delta=" Then conclude.")),
        PartEndEvent(index=0, part=ThinkingPart(content="First, let me think... Then conclude.")),
    ]

    # ------------------------------------------------------------------ #
    # 4. Multi-step run: text -> tool call + response -> text.
    # Pydantic AI restarts part indices at 0 for each model response; the
    # converter assigns globally-monotonic indices to Agentex messages.
    # ------------------------------------------------------------------ #
    multi_step_pydantic = [
        # First model turn: text then tool call
        PartStartEvent(index=0, part=TextPart(content="")),
        PartDeltaEvent(index=0, delta=TextPartDelta(content_delta="Let me check the weather.")),
        PartEndEvent(index=0, part=TextPart(content="Let me check the weather.")),
        PartStartEvent(
            index=1,
            part=ToolCallPart(tool_name="get_weather", args=None, tool_call_id="call_ms1"),
        ),
        PartDeltaEvent(
            index=1,
            delta=ToolCallPartDelta(args_delta='{"city":"London"}', tool_call_id="call_ms1"),
        ),
        PartEndEvent(
            index=1,
            part=ToolCallPart(tool_name="get_weather", args='{"city":"London"}', tool_call_id="call_ms1"),
        ),
        FunctionToolResultEvent(
            part=ToolReturnPart(tool_name="get_weather", content="Cloudy, 15C", tool_call_id="call_ms1"),
        ),
        # Second model turn: text response (pydantic restarts index at 0)
        PartStartEvent(index=0, part=TextPart(content="")),
        PartDeltaEvent(index=0, delta=TextPartDelta(content_delta="It's cloudy and 15C in London.")),
        PartEndEvent(index=0, part=TextPart(content="It's cloudy and 15C in London.")),
    ]

    text_only_events = asyncio.run(_canonical(text_only_pydantic))
    tool_call_events = asyncio.run(_canonical(tool_call_pydantic))
    reasoning_events = asyncio.run(_canonical(reasoning_pydantic))
    multi_step_events = asyncio.run(_canonical(multi_step_pydantic))

    return [
        Fixture(name="pydantic-ai-text-only", events=text_only_events),
        Fixture(name="pydantic-ai-single-tool-call", events=tool_call_events),
        Fixture(name="pydantic-ai-reasoning-block", events=reasoning_events),
        Fixture(name="pydantic-ai-multi-step", events=multi_step_events),
    ]


_FIXTURES: list[Fixture] = _build_fixtures()

for _f in _FIXTURES:
    register(_f)


# ---------------------------------------------------------------------------
# Cross-channel conformance: logical equivalence + span equivalence
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fixture", _FIXTURES, ids=lambda f: f.name)
@pytest.mark.asyncio
async def test_cross_channel_equivalence(fixture: Fixture) -> None:
    """Assert that yield_events and auto_send produce equivalent logical
    deliveries and identical span signals for each pydantic-ai fixture.

    See runner.py for the full contract. The AGX1-377 note at the top of this
    module explains why streamed-tool-request delivery is not yet asserted.
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


@pytest.mark.parametrize("fixture", _FIXTURES, ids=lambda f: f.name)
def test_span_derivation_is_deterministic(fixture: Fixture) -> None:
    """Span derivation over the same event list is idempotent."""
    assert derive_all(fixture.events) == derive_all(fixture.events)
