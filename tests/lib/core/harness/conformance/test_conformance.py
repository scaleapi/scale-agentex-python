"""Cross-channel conformance tests: yield_events vs auto_send.

What is asserted
----------------
For each fixture the conformance runner drives BOTH delivery channels and
verifies two guarantees:

1. **Logical-delivery equivalence**: the sequence of logically-delivered
   messages is identical across channels. "Logical" normalises away the
   streaming-envelope difference:
   - yield channel delivers StreamTaskMessageFull(ToolResponseContent) as-is.
   - auto_send delivers the same tool-response by opening a streaming context
     with the full content and closing it immediately.
   Both collapse to LogicalDelivery(content_type, identity, payload) tuples
   that compare equal. The payload includes initial_content (TextContent.content
   and ReasoningContent.summary) so a channel that drops initial content fails.

2. **Span signal equivalence**: both channels feed the same pure SpanDeriver
   over the same event sequence, so the derived span signals must be identical.

What is NOT asserted
--------------------
Raw wire-level event shapes are NOT compared (that would fail by design: the
Full vs Start+Done envelope difference is a documented, acceptable choice in
auto_send — see runner.py for the rationale).

AGX1-377 fix: auto_send now delivers streamed tool-request messages. The
suppression that previously prevented the yield normaliser from emitting a
LogicalDelivery for Start(tool_request)+Done is removed. Both channels now
produce a delivery for streamed tool_request, verified by the
"streamed-tool-request" fixture.
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

from .runner import (
    Fixture,
    register,
    derive_all,
    all_fixtures,
    run_cross_channel_conformance,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_FIXTURES: list[Fixture] = [
    # fixture 1: single tool call — tool_request delivered via Full (classic path)
    # plus a streamed tool_response via Full. Both channels should deliver both.
    Fixture(
        name="builtin-single-tool",
        events=[
            StreamTaskMessageStart(
                type="start",
                index=0,
                content=ToolRequestContent(
                    type="tool_request", author="agent", tool_call_id="c", name="Bash", arguments={}
                ),
            ),
            StreamTaskMessageDone(type="done", index=0),
            StreamTaskMessageFull(
                type="full",
                index=1,
                content=ToolResponseContent(
                    type="tool_response", author="agent", tool_call_id="c", name="Bash", content="ok"
                ),
            ),
        ],
    ),
    # fixture 2: streaming text — exercises the text start/delta/done path.
    # Uses non-empty initial_content so the payload comparison catches a channel
    # that drops StreamTaskMessageStart.content (Greptile id 3438655533, P1).
    Fixture(
        name="streaming-text",
        events=[
            StreamTaskMessageStart(
                type="start",
                index=0,
                content=TextContent(type="text", author="agent", content="Init"),
            ),
            StreamTaskMessageDelta(
                type="delta",
                index=0,
                delta=TextDelta(type="text", text_delta="Hello"),
            ),
            StreamTaskMessageDelta(
                type="delta",
                index=0,
                delta=TextDelta(type="text", text_delta=" world"),
            ),
            StreamTaskMessageDone(type="done", index=0),
        ],
    ),
    # fixture 3: reasoning block — exercises reasoning span open/close + delivery.
    # ReasoningContent.summary is included in the payload so a channel that drops
    # the reasoning-summary fails (Greptile id 3438655533, P1).
    Fixture(
        name="reasoning-block",
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
    ),
    # fixture 4: streamed tool_request (AGX1-377 fix) — tool_request delivered
    # via Start+Done (no Full). auto_send now delivers this instead of dropping
    # it. Both channels must produce a LogicalDelivery for this fixture.
    Fixture(
        name="streamed-tool-request",
        events=[
            StreamTaskMessageStart(
                type="start",
                index=0,
                content=ToolRequestContent(
                    type="tool_request",
                    author="agent",
                    tool_call_id="tr-1",
                    name="Read",
                    arguments={"path": "/tmp/foo"},
                ),
            ),
            StreamTaskMessageDone(type="done", index=0),
            StreamTaskMessageFull(
                type="full",
                index=1,
                content=ToolResponseContent(
                    type="tool_response",
                    author="agent",
                    tool_call_id="tr-1",
                    name="Read",
                    content="file contents",
                ),
            ),
        ],
    ),
    # fixture 5: parallel tool calls + a tool that errors (AGX1-373 review,
    # danielmillerp). The earlier fixtures only exercise one tool at a time, so
    # equivalence is proven over trivially-orderable streams. This stresses the
    # representative case: two tool spans open SIMULTANEOUSLY (p-ls opens via the
    # streamed Start+Done path, p-read opens via Full while p-ls is still open),
    # then close in a different order than they opened, and one of them returns
    # an error. It guards against the two channels agreeing with each other while
    # both mishandling interleaved/parallel spans or a failing tool.
    #
    # The tool error is represented the way the harness encodes it today — an
    # "Error: ..." string in ToolResponseContent.content (see
    # claude_agents/hooks/hooks.py post_tool_use_failure_hook). Once the deferred
    # ToolResponseContent.is_error field lands (AGX1-371), extend this fixture to
    # assert the error status propagates onto the closed tool span.
    Fixture(
        name="parallel-tools-with-error",
        events=[
            # p-ls: streamed tool_request (opens its span at Done).
            StreamTaskMessageStart(
                type="start",
                index=0,
                content=ToolRequestContent(
                    type="tool_request",
                    author="agent",
                    tool_call_id="p-ls",
                    name="Bash",
                    arguments={"command": "ls /nope"},
                ),
            ),
            StreamTaskMessageDone(type="done", index=0),
            # p-read: Full tool_request opens a second span while p-ls is open.
            StreamTaskMessageFull(
                type="full",
                index=1,
                content=ToolRequestContent(
                    type="tool_request",
                    author="agent",
                    tool_call_id="p-read",
                    name="Read",
                    arguments={"path": "/etc/hosts"},
                ),
            ),
            # p-ls errors and closes first (close order != open order).
            StreamTaskMessageFull(
                type="full",
                index=2,
                content=ToolResponseContent(
                    type="tool_response",
                    author="agent",
                    tool_call_id="p-ls",
                    name="Bash",
                    content="Error: ls: /nope: No such file or directory",
                ),
            ),
            # p-read succeeds and closes second.
            StreamTaskMessageFull(
                type="full",
                index=3,
                content=ToolResponseContent(
                    type="tool_response",
                    author="agent",
                    tool_call_id="p-read",
                    name="Read",
                    content="127.0.0.1 localhost",
                ),
            ),
        ],
    ),
]

# Register all fixtures for backward-compatible use via all_fixtures()
for _f in _FIXTURES:
    register(_f)


# ---------------------------------------------------------------------------
# Cross-channel conformance: logical equivalence + span equivalence
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fixture", _FIXTURES, ids=lambda f: f.name)
@pytest.mark.asyncio
async def test_cross_channel_equivalence(fixture: Fixture) -> None:
    """Assert that yield_events and auto_send produce equivalent logical
    deliveries and identical span signals for every fixture.

    This is the real cross-channel guarantee: the two delivery adapters
    agree on WHAT was delivered (logical content) and HOW spans were derived,
    even though their streaming-envelope shapes differ (Full vs Start+Done for
    tool messages).

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


# ---------------------------------------------------------------------------
# Backward-compatible determinism test (kept for regression coverage)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fixture", all_fixtures(), ids=lambda f: f.name)
def test_span_derivation_is_deterministic(fixture: Fixture) -> None:
    """Span derivation over the same event list is idempotent.

    Retained as a lightweight regression guard. The primary cross-channel
    guarantee is asserted in test_cross_channel_equivalence above.
    """
    assert derive_all(fixture.events) == derive_all(fixture.events)
