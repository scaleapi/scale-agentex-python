"""Auto-send delivery: canonical stream -> adk.streaming side effects + tracing."""

from __future__ import annotations

from typing import Any, AsyncIterator
from datetime import datetime

from agentex.types.text_delta import TextDelta
from agentex.types.text_content import TextContent
from agentex.lib.core.harness.types import TurnUsage, TurnResult, StreamTaskMessage
from agentex.lib.core.harness.tracer import SpanTracer
from agentex.types.task_message_update import (
    StreamTaskMessageDone,
    StreamTaskMessageFull,
    StreamTaskMessageDelta,
    StreamTaskMessageStart,
)
from agentex.lib.core.harness.span_derivation import SpanDeriver


async def auto_send(
    events: AsyncIterator[StreamTaskMessage],
    task_id: str,
    tracer: SpanTracer | None = None,
    streaming: Any = None,
    usage: TurnUsage | None = None,
    created_at: datetime | None = None,
) -> TurnResult:
    """Push the canonical stream to the task stream via adk.streaming.

    Opens a streaming context per message (keyed by index), streams deltas via
    ctx.stream_update, and closes via ctx.close() on Done. Posts tool
    request/response full messages by opening a context with the content and
    closing it immediately (no deltas). Derives and traces spans from the same
    stream. Returns the last text segment's text + usage.

    Index-keyed routing: each Start(index=i) opens a context stored in
    ctx_map[i]; Delta(index=i) routes to ctx_map.get(i); Done(index=i) closes
    and removes ctx_map[i]. Events with index is None are skipped. The finally
    block closes all remaining open contexts.

    final_text last-segment semantics: a new Start(TextContent) resets
    final_text_parts so that multi-step turns return the LAST text segment.
    Full(TextContent) also overwrites final_text_parts (same semantics).

    AGX1-378: created_at is forwarded to every streaming_task_message_context
    call so callers can back-date message timestamps.

    Mirrors the open/close/stream_update pattern from
    src/agentex/lib/adk/_modules/_langgraph_async.py:
      - context opened via streaming_task_message_context(...).__aenter__()
      - context closed via ctx.close() (not __aexit__)
      - deltas pushed as StreamTaskMessageDelta with parent_task_message set
        from ctx.task_message

    For async + temporal agents (call from inside an activity).
    """
    if streaming is None:
        from agentex.lib import adk

        streaming = adk.streaming

    deriver = SpanDeriver() if tracer is not None else None
    final_text_parts: list[str] = []
    ctx_map: dict[int, Any] = {}

    async def _close_all() -> None:
        for ctx in list(ctx_map.values()):
            await ctx.close()
        ctx_map.clear()

    try:
        async for event in events:
            if deriver is not None and tracer is not None:
                for signal in deriver.observe(event):
                    await tracer.handle(signal)

            if isinstance(event, StreamTaskMessageStart):
                if event.index is None:
                    continue
                i = event.index
                # Reset final_text_parts when a new text segment starts
                if isinstance(event.content, TextContent):
                    final_text_parts = []
                ctx = streaming.streaming_task_message_context(
                    task_id=task_id,
                    initial_content=event.content,
                    created_at=created_at,
                )
                ctx_map[i] = await ctx.__aenter__()

            elif isinstance(event, StreamTaskMessageDelta):
                if event.index is None:
                    continue
                ctx = ctx_map.get(event.index)
                if ctx is not None and event.delta is not None:
                    # Reconstruct the delta with parent_task_message set from
                    # the context's task_message (mirrors _langgraph_async.py
                    # lines 72-78 and 117-127).
                    delta_with_parent = StreamTaskMessageDelta(
                        parent_task_message=ctx.task_message,
                        delta=event.delta,
                        type="delta",
                        index=event.index,
                    )
                    await ctx.stream_update(delta_with_parent)
                    if isinstance(event.delta, TextDelta) and event.delta.text_delta:
                        final_text_parts.append(event.delta.text_delta)

            elif isinstance(event, StreamTaskMessageDone):
                if event.index is None:
                    continue
                ctx = ctx_map.pop(event.index, None)
                if ctx is not None:
                    await ctx.close()

            elif isinstance(event, StreamTaskMessageFull):
                # Full messages: post the full message by opening a context
                # with the content and closing it immediately (no deltas;
                # StreamingTaskMessageContext.close() persists initial_content
                # when the accumulator is empty). Use async with so the context
                # is closed even if close() raises (__aexit__ delegates to
                # close()).
                # Full(TextContent) also resets final_text_parts for
                # last-segment semantics.
                if isinstance(event.content, TextContent):
                    final_text_parts = [event.content.content]
                async with streaming.streaming_task_message_context(
                    task_id=task_id,
                    initial_content=event.content,
                    created_at=created_at,
                ):
                    pass

    finally:
        await _close_all()
        if deriver is not None and tracer is not None:
            for signal in deriver.flush():
                await tracer.handle(signal)

    return TurnResult(final_text="".join(final_text_parts), usage=usage or TurnUsage())
