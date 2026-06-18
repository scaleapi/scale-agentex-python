"""Auto-send delivery: canonical stream -> adk.streaming side effects + tracing."""

from __future__ import annotations

from typing import Any, AsyncIterator

from agentex.types.task_message_update import (
    StreamTaskMessageDelta,
    StreamTaskMessageDone,
    StreamTaskMessageFull,
    StreamTaskMessageStart,
)
from agentex.types.text_delta import TextDelta

from agentex.lib.core.harness.span_derivation import SpanDeriver
from agentex.lib.core.harness.tracer import SpanTracer
from agentex.lib.core.harness.types import StreamTaskMessage, TurnResult, TurnUsage


async def auto_send(
    events: AsyncIterator[StreamTaskMessage],
    task_id: str,
    tracer: SpanTracer | None = None,
    streaming: Any = None,
    usage: TurnUsage | None = None,
) -> TurnResult:
    """Push the canonical stream to the task stream via adk.streaming.

    Opens a streaming context per text/reasoning message, streams deltas via
    ctx.stream_update, and closes via ctx.close() on Done. Posts tool
    request/response full messages by opening a context with the content and
    closing it immediately (no deltas). Derives and traces spans from the same
    stream. Returns the accumulated final text + usage.

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
    current_ctx: Any = None

    async def _close_current() -> None:
        nonlocal current_ctx
        if current_ctx is not None:
            await current_ctx.close()
            current_ctx = None

    try:
        async for event in events:
            if deriver is not None:
                for signal in deriver.observe(event):
                    await tracer.handle(signal)  # type: ignore[union-attr]

            if isinstance(event, StreamTaskMessageStart):
                ctype = getattr(event.content, "type", None)
                if ctype in ("text", "reasoning"):
                    await _close_current()
                    ctx = streaming.streaming_task_message_context(
                        task_id=task_id,
                        initial_content=event.content,
                    )
                    current_ctx = await ctx.__aenter__()

            elif isinstance(event, StreamTaskMessageDelta):
                if current_ctx is not None and event.delta is not None:
                    # Reconstruct the delta with parent_task_message set from
                    # the context's task_message (mirrors _langgraph_async.py
                    # lines 72-78 and 117-127).
                    delta_with_parent = StreamTaskMessageDelta(
                        parent_task_message=current_ctx.task_message,
                        delta=event.delta,
                        type="delta",
                        index=event.index,
                    )
                    await current_ctx.stream_update(delta_with_parent)
                    if isinstance(event.delta, TextDelta) and event.delta.text_delta:
                        final_text_parts.append(event.delta.text_delta)

            elif isinstance(event, StreamTaskMessageDone):
                await _close_current()

            elif isinstance(event, StreamTaskMessageFull):
                # Full messages (tool_request / tool_response): close any open
                # streaming context first, then post the full message by opening
                # a context with the content and closing it immediately
                # (no deltas; StreamingTaskMessageContext.close() persists
                # initial_content when the accumulator is empty). Use async with
                # so the context is closed even if close() raises (__aexit__
                # delegates to close()).
                await _close_current()
                async with streaming.streaming_task_message_context(
                    task_id=task_id,
                    initial_content=event.content,
                ):
                    pass

    finally:
        await _close_current()
        if deriver is not None:
            for signal in deriver.flush():
                await tracer.handle(signal)  # type: ignore[union-attr]

    return TurnResult(final_text="".join(final_text_parts), usage=usage or TurnUsage())
