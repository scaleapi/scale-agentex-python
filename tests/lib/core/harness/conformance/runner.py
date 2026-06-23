"""Shared conformance engine: every harness tap registers fixtures here.

A fixture is (name, list[StreamTaskMessage]). The runner asserts two things:

1. **Cross-channel logical equivalence**: yield_events and auto_send produce the
   same *logical* sequence of delivered message contents. "Logical" means we
   normalise away the streaming-envelope difference:
   - yield channel delivers StreamTaskMessageFull(ToolResponseContent) verbatim.
   - auto_send channel delivers the same tool-response by opening a streaming
     context with the full content and closing it immediately (Start+Done on the
     wire), not a Full event.
   Both reduce to the same LogicalDelivery(type, identity, payload) tuple; the
   conformance test compares those normalised sequences.

   `payload` carries the content that callers actually consume:
   - text: initial_content.content prepended, then accumulated delta string
   - reasoning: initial_content.summary joined, then accumulated delta string
   - tool_request: the arguments dict (JSON-sorted), from Start content
   - tool_response: the content value (str)
   This catches a channel that delivers the right structural shape but corrupts,
   drops, or omits initial_content (including reasoning summary) or payload.

2. **Span signal equivalence**: each channel is driven with its own recording
   tracer that captures every SpanSignal it actually receives in handle(); the
   two channels' recorded signal lists must be identical. Comparing what each
   channel genuinely emitted (rather than re-deriving from the events) catches a
   regression where a channel skips deriver.observe() for some event type.

Registry shared-state hazard: `_REGISTRY` is process-global. Every `test_*.py`
module that calls `register()` at import time contributes to it, so a module
that parametrizes over `all_fixtures()` will see fixtures registered by ANY
other conformance module imported earlier in the same pytest process (collection
order is not guaranteed). To stay deterministic, each future harness conformance
module should register and parametrize over its OWN fixtures (e.g. keep a
module-local list it both registers and parametrizes), rather than relying on
cross-module global accumulation via `all_fixtures()`.

Design decision — Full-message handling in auto_send
----------------------------------------------------
auto_send posts a StreamTaskMessageFull (tool_request or tool_response) by
opening a streaming context with the full content and closing it immediately,
rather than calling adk.messages.create. This open+close approach is retained
because:
  - StreamingTaskMessageContext.close() persists initial_content when no deltas
    have been streamed, so the message IS correctly persisted.
  - It mirrors the pattern already used by the real langgraph streaming helper
    (now in _langgraph_turn.py), keeping behavioural parity.
  - Switching to adk.messages.create would require an additional injectable
    dependency, adding surface area for no observable benefit.
The conformance test treats this as an ACCEPTABLE envelope difference: at the
logical-content level, Full(ToolResponseContent) from yield and
Start(content)+Done from auto_send are equivalent. The recorded span signals are
identical because both adapters drive the same SpanDeriver.observe() call
sequence and forward every signal to their tracer.

auto_send DELIVERS streamed tool-request messages (Start+Done): both channels
produce a LogicalDelivery for a streamed tool_request, and the cross-channel
assertion verifies it is delivered on both.
"""

from __future__ import annotations

import json
from typing import Any, NamedTuple, override
from dataclasses import dataclass

from agentex.types.text_delta import TextDelta
from agentex.types.task_message import TaskMessage
from agentex.lib.core.harness.types import SpanSignal, StreamTaskMessage
from agentex.lib.core.harness.tracer import SpanTracer
from agentex.types.task_message_update import (
    StreamTaskMessageDone,
    StreamTaskMessageFull,
    StreamTaskMessageDelta,
    StreamTaskMessageStart,
)
from agentex.types.reasoning_content_delta import ReasoningContentDelta
from agentex.lib.core.harness.span_derivation import SpanDeriver

from .._fakes import FakeTracing


@dataclass
class Fixture:
    name: str
    events: list[StreamTaskMessage]


_REGISTRY: list[Fixture] = []


def register(fixture: Fixture) -> None:
    _REGISTRY.append(fixture)


def all_fixtures() -> list[Fixture]:
    return list(_REGISTRY)


def derive_all(events: list[StreamTaskMessage]) -> list[SpanSignal]:
    d = SpanDeriver()
    out: list[SpanSignal] = []
    for e in events:
        out.extend(d.observe(e))
    out.extend(d.flush())
    return out


# ---------------------------------------------------------------------------
# Logical delivery normalisation
# ---------------------------------------------------------------------------


class LogicalDelivery(NamedTuple):
    """A single logically-delivered message, channel-agnostic.

    `content_type` is the .type of the content (e.g. "text", "reasoning",
    "tool_request", "tool_response"). `identity` is a frozenset of key=value
    pairs that uniquely identify the content (e.g. tool_call_id for tool
    messages, or index for text/reasoning). `payload` is a stable string
    representation of the content callers actually consume:
    - text: initial_content.content prepended to accumulated delta strings
    - reasoning: initial_content.summary joined, prepended to accumulated
      reasoning-content delta strings
    - tool_request: JSON-sorted arguments from Start content
    - tool_response: str(content) from Full event
    """

    content_type: str
    identity: frozenset[tuple[str, Any]]
    payload: str = ""


def _yield_logical_deliveries(events: list[StreamTaskMessage]) -> list[LogicalDelivery]:
    """Extract logical deliveries from the yield channel's event list.

    The yield channel forwards events verbatim. A logical delivery is:
    - A Full event (tool_request / tool_response): content delivered as-is.
    - A Start + ... + Done sequence for text/reasoning/tool_request content.

    The `payload` field captures the content callers consume:
    - text: initial_content.content (from Start) prepended to accumulated deltas
    - reasoning: initial_content.summary joined (from Start) prepended to
      accumulated reasoning-content deltas (this catches a channel that drops
      the summary)
    - tool_request: JSON-sorted arguments from the Start content (delivered on
      both channels)
    - tool_response: str(content) from Full event
    """
    from agentex.types.text_content import TextContent
    from agentex.types.reasoning_content import ReasoningContent
    from agentex.types.tool_request_content import ToolRequestContent

    deliveries: list[LogicalDelivery] = []
    # Track which indices had a Start so we can pair with Done
    started: dict[int, Any] = {}  # index -> initial content
    # Accumulate delta text per index (seed with initial_content text if present)
    accumulated: dict[int, list[str]] = {}  # index -> list of delta strings

    for event in events:
        if isinstance(event, StreamTaskMessageStart):
            if event.index is not None:
                started[event.index] = event.content
                # Seed accumulator with initial_content so a channel that drops
                # initial_content but delivers deltas correctly will fail.
                seed: list[str] = []
                if isinstance(event.content, TextContent) and event.content.content:
                    seed = [event.content.content]
                elif isinstance(event.content, ReasoningContent) and event.content.summary:
                    seed = list(event.content.summary)
                accumulated[event.index] = seed
        elif isinstance(event, StreamTaskMessageDelta):
            if event.index is not None and event.delta is not None:
                if isinstance(event.delta, TextDelta) and event.delta.text_delta:
                    accumulated.setdefault(event.index, []).append(event.delta.text_delta)
                elif isinstance(event.delta, ReasoningContentDelta) and event.delta.content_delta:
                    accumulated.setdefault(event.index, []).append(event.delta.content_delta)
        elif isinstance(event, StreamTaskMessageDone):
            if event.index is not None and event.index in started:
                content = started.pop(event.index)
                deltas = accumulated.pop(event.index, [])
                ctype = getattr(content, "type", None) or ""
                if ctype in ("text", "reasoning"):
                    deliveries.append(
                        LogicalDelivery(
                            content_type=ctype,
                            identity=frozenset({("index", event.index)}),
                            payload="".join(deltas),
                        )
                    )
                elif ctype == "tool_request" and isinstance(content, ToolRequestContent):
                    # auto_send delivers streamed tool-request messages. Emit a
                    # delivery here so the cross-channel assertion verifies it is
                    # present on both channels.
                    deliveries.append(
                        LogicalDelivery(
                            content_type=ctype,
                            identity=frozenset(
                                {
                                    ("tool_call_id", content.tool_call_id),
                                    ("name", content.name),
                                }
                            ),
                            payload=json.dumps(content.arguments, sort_keys=True),
                        )
                    )
        elif isinstance(event, StreamTaskMessageFull):
            content = event.content
            ctype = getattr(content, "type", None) or ""
            if ctype == "tool_response":
                from agentex.types.tool_response_content import ToolResponseContent

                if isinstance(content, ToolResponseContent):
                    deliveries.append(
                        LogicalDelivery(
                            content_type=ctype,
                            identity=frozenset(
                                {
                                    ("tool_call_id", content.tool_call_id),
                                    ("name", content.name),
                                }
                            ),
                            payload=str(content.content),
                        )
                    )
            elif ctype == "tool_request":
                from agentex.types.tool_request_content import ToolRequestContent

                if isinstance(content, ToolRequestContent):
                    deliveries.append(
                        LogicalDelivery(
                            content_type=ctype,
                            identity=frozenset(
                                {
                                    ("tool_call_id", content.tool_call_id),
                                    ("name", content.name),
                                }
                            ),
                            payload=json.dumps(content.arguments, sort_keys=True),
                        )
                    )

    return deliveries


# ---------------------------------------------------------------------------
# Fake streaming backend for auto_send conformance runner
# ---------------------------------------------------------------------------


class _FakeCtx:
    """Mirrors StreamingTaskMessageContext: __aenter__ opens, close() closes."""

    def __init__(self, sink: list[Any], content_type: str, initial_content: Any) -> None:
        self.sink = sink
        self.content_type = content_type
        self.task_message = TaskMessage(
            id="msg-conformance",
            task_id="conformance-task",
            content=initial_content,
        )

    async def __aenter__(self) -> "_FakeCtx":
        self.sink.append(("open", self.content_type, self.task_message.content))
        return self

    async def __aexit__(self, *args: Any) -> bool:
        await self.close()
        return False

    async def close(self) -> None:
        self.sink.append(("close", self.content_type))

    async def stream_update(self, update: Any) -> Any:
        self.sink.append(("update", update))
        return update


class _FakeStreaming:
    """Fake streaming backend; records every context lifecycle event."""

    def __init__(self) -> None:
        self.sink: list[Any] = []

    def streaming_task_message_context(
        self,
        task_id: str,
        initial_content: Any,
        streaming_mode: str = "coalesced",
        created_at: Any = None,
    ) -> _FakeCtx:
        ctype = getattr(initial_content, "type", None) or ""
        self.sink.append(("ctx", ctype, initial_content))
        return _FakeCtx(self.sink, ctype, initial_content)


class _RecordingTracer(SpanTracer):
    """SpanTracer that records every SpanSignal it actually receives.

    Each delivery channel calls `tracer.handle(signal)` for every signal it
    derives from the stream, so `received_signals` captures what the channel
    genuinely emitted — not a re-derivation. Comparing the two channels'
    recorded lists catches regressions where a channel skips
    `deriver.observe(event)` for some event type.
    """

    def __init__(self, tracing: Any) -> None:
        super().__init__(
            trace_id="conformance-trace",
            parent_span_id="conformance-parent",
            tracing=tracing,
        )
        self.received_signals: list[SpanSignal] = []

    @override
    async def handle(self, signal: SpanSignal) -> None:
        self.received_signals.append(signal)
        await super().handle(signal)


async def _gen(events: list[StreamTaskMessage]):  # type: ignore[return]
    for e in events:
        yield e


def _auto_send_logical_deliveries(sink: list[Any]) -> list[LogicalDelivery]:
    """Extract logical deliveries from the auto_send fake streaming sink.

    Each context lifecycle in the sink looks like:
      ("ctx", ctype, content)  -- context created
      ("open", ctype, content) -- context __aenter__
      [("update", delta), ...]  -- optional deltas (StreamTaskMessageDelta)
      ("close", ctype)          -- context closed

    A logical delivery corresponds to each open+close pair. For text/reasoning
    we identify by sequential position and build the payload by prepending the
    initial_content text (TextContent.content) or summary (ReasoningContent.summary)
    to accumulated deltas. This matches _yield_logical_deliveries so a channel
    that drops initial_content or reasoning summary fails the comparison.
    For tool messages we use tool_call_id + name and capture arguments/content.
    """
    from agentex.types.text_content import TextContent
    from agentex.types.reasoning_content import ReasoningContent
    from agentex.types.tool_request_content import ToolRequestContent
    from agentex.types.tool_response_content import ToolResponseContent

    deliveries: list[LogicalDelivery] = []
    open_idx = 0
    while open_idx < len(sink):
        entry = sink[open_idx]
        if entry[0] == "ctx":
            ctype: str = entry[1]
            content: Any = entry[2]
            found_open = False
            delta_parts: list[str] = []
            # Seed delta_parts with initial_content so payload comparison
            # catches a channel that drops initial_content but delivers deltas.
            if isinstance(content, TextContent) and content.content:
                delta_parts = [content.content]
            elif isinstance(content, ReasoningContent) and content.summary:
                delta_parts = list(content.summary)
            for j in range(open_idx + 1, len(sink)):
                if sink[j][0] == "open" and sink[j][1] == ctype and not found_open:
                    found_open = True
                elif found_open and sink[j][0] == "update":
                    # Accumulate delta content from StreamTaskMessageDelta
                    update = sink[j][1]
                    if isinstance(update, StreamTaskMessageDelta) and update.delta is not None:
                        if isinstance(update.delta, TextDelta) and update.delta.text_delta:
                            delta_parts.append(update.delta.text_delta)
                        elif isinstance(update.delta, ReasoningContentDelta) and update.delta.content_delta:
                            delta_parts.append(update.delta.content_delta)
                elif sink[j][0] == "close" and sink[j][1] == ctype and found_open:
                    # Matched open+close: emit logical delivery with payload
                    if ctype in ("text", "reasoning"):
                        count = sum(1 for k in range(open_idx) if sink[k][0] == "ctx" and sink[k][1] == ctype)
                        deliveries.append(
                            LogicalDelivery(
                                content_type=ctype,
                                identity=frozenset({("seq", count)}),
                                payload="".join(delta_parts),
                            )
                        )
                    elif ctype == "tool_response":
                        if isinstance(content, ToolResponseContent):
                            deliveries.append(
                                LogicalDelivery(
                                    content_type=ctype,
                                    identity=frozenset(
                                        {
                                            ("tool_call_id", content.tool_call_id),
                                            ("name", content.name),
                                        }
                                    ),
                                    payload=str(content.content),
                                )
                            )
                    elif ctype == "tool_request":
                        if isinstance(content, ToolRequestContent):
                            deliveries.append(
                                LogicalDelivery(
                                    content_type=ctype,
                                    identity=frozenset(
                                        {
                                            ("tool_call_id", content.tool_call_id),
                                            ("name", content.name),
                                        }
                                    ),
                                    payload=json.dumps(content.arguments, sort_keys=True),
                                )
                            )
                    open_idx = j + 1
                    break
            else:
                open_idx += 1
        else:
            open_idx += 1

    return deliveries


def _yield_text_reasoning_seq(deliveries: list[LogicalDelivery]) -> list[LogicalDelivery]:
    """Re-key text/reasoning deliveries from index-based to seq-based identity.

    The yield channel uses event.index as identity; auto_send uses a sequential
    counter. To compare across channels, normalise both to sequential position
    within each content type.
    """
    result: list[LogicalDelivery] = []
    counts: dict[str, int] = {}
    for d in deliveries:
        if d.content_type in ("text", "reasoning"):
            seq = counts.get(d.content_type, 0)
            counts[d.content_type] = seq + 1
            result.append(
                LogicalDelivery(
                    content_type=d.content_type,
                    identity=frozenset({("seq", seq)}),
                    payload=d.payload,
                )
            )
        else:
            result.append(d)
    return result


async def run_cross_channel_conformance(
    fixture: Fixture,
) -> tuple[list[LogicalDelivery], list[LogicalDelivery], list[SpanSignal], list[SpanSignal]]:
    """Run both channels over a fixture; return (yield_deliveries, auto_deliveries,
    yield_spans, auto_spans).

    The caller asserts yield_deliveries == auto_deliveries and
    yield_spans == auto_spans. The span signals are the ones each channel's
    tracer ACTUALLY recorded while delivering (not a re-derivation), so a
    regression where a channel skips deriver.observe() for some event type is
    caught.
    """
    from agentex.lib.core.harness.auto_send import auto_send
    from agentex.lib.core.harness.yield_delivery import yield_events

    # --- yield channel ---
    tracer_yield = _RecordingTracer(tracing=FakeTracing())
    yield_out = [e async for e in yield_events(_gen(fixture.events), tracer=tracer_yield)]

    # Span signals the yield channel actually emitted to its tracer
    yield_spans = tracer_yield.received_signals

    # Logical deliveries from yield output
    yield_deliveries = _yield_text_reasoning_seq(_yield_logical_deliveries(yield_out))

    # --- auto_send channel ---
    tracer_auto = _RecordingTracer(tracing=FakeTracing())
    fake_streaming = _FakeStreaming()
    await auto_send(
        _gen(fixture.events),
        task_id="conformance-task",
        tracer=tracer_auto,
        streaming=fake_streaming,
    )

    # Span signals the auto_send channel actually emitted to its tracer
    auto_spans = tracer_auto.received_signals

    # Logical deliveries from what the streaming backend received
    auto_deliveries = _auto_send_logical_deliveries(fake_streaming.sink)

    return yield_deliveries, auto_deliveries, yield_spans, auto_spans
