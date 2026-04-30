from __future__ import annotations

import asyncio
import contextlib
import json
from typing import Awaitable, Callable, Literal

from agentex import AsyncAgentex
from agentex.lib.utils.logging import make_logger
from agentex.types.data_content import DataContent
from agentex.types.task_message import (
    TaskMessage,
    TaskMessageContent,
)
from agentex.types.text_content import TextContent
from agentex.types.reasoning_content import ReasoningContent
from agentex.types.task_message_delta import (
    DataDelta,
    TextDelta,
    ToolRequestDelta,
    ToolResponseDelta,
    ReasoningContentDelta,
    ReasoningSummaryDelta,
)
from agentex.types.task_message_update import (
    TaskMessageDelta,
    TaskMessageUpdate,
    StreamTaskMessageDone,
    StreamTaskMessageFull,
    StreamTaskMessageDelta,
    StreamTaskMessageStart,
)
from agentex.types.tool_request_content import ToolRequestContent
from agentex.types.tool_response_content import ToolResponseContent
from agentex.lib.core.adapters.streams.port import StreamRepository

logger = make_logger(__name__)


def _get_stream_topic(task_id: str) -> str:
    return f"task:{task_id}"


StreamingMode = Literal["off", "per_token", "coalesced"]
"""Controls how a StreamingTaskMessageContext publishes deltas.

- "off":        Feed the accumulator (so the persisted message body is correct)
                but never publish per-delta events. Consumers see start + done
                only. Lowest latency.
- "per_token":  Publish every delta immediately. Highest UX fidelity for
                token-by-token rendering, highest Redis cost, and re-introduces
                head-of-line blocking on the producer's event loop.
- "coalesced":  Buffer deltas in a small time/size window and publish them as
                merged batches. The first delta flushes immediately for fast
                perceived responsiveness; subsequent deltas flush every 50ms or
                whenever 128 buffered chars accumulate, whichever comes first.
                Order within each (delta type, index) channel is preserved
                exactly; only granularity changes.
"""


def _delta_char_len(delta: TaskMessageDelta | None) -> int:
    if delta is None:
        return 0
    if isinstance(delta, TextDelta):
        return len(delta.text_delta or "")
    if isinstance(delta, DataDelta):
        return len(delta.data_delta or "")
    if isinstance(delta, ReasoningSummaryDelta):
        return len(delta.summary_delta or "")
    if isinstance(delta, ReasoningContentDelta):
        return len(delta.content_delta or "")
    if isinstance(delta, ToolRequestDelta):
        return len(delta.arguments_delta or "")
    if isinstance(delta, ToolResponseDelta):
        return len(delta.content_delta or "")
    return 0


def _can_merge(a: TaskMessageDelta, b: TaskMessageDelta) -> bool:
    if type(a) is not type(b):
        return False
    if isinstance(a, ReasoningSummaryDelta) and isinstance(b, ReasoningSummaryDelta):
        return a.summary_index == b.summary_index
    if isinstance(a, ReasoningContentDelta) and isinstance(b, ReasoningContentDelta):
        return a.content_index == b.content_index
    if isinstance(a, ToolRequestDelta) and isinstance(b, ToolRequestDelta):
        return a.tool_call_id == b.tool_call_id
    if isinstance(a, ToolResponseDelta) and isinstance(b, ToolResponseDelta):
        return a.tool_call_id == b.tool_call_id
    return True


def _merge_pair(a: TaskMessageDelta, b: TaskMessageDelta) -> TaskMessageDelta:
    if isinstance(a, TextDelta) and isinstance(b, TextDelta):
        return TextDelta(type="text", text_delta=(a.text_delta or "") + (b.text_delta or ""))
    if isinstance(a, DataDelta) and isinstance(b, DataDelta):
        return DataDelta(type="data", data_delta=(a.data_delta or "") + (b.data_delta or ""))
    if isinstance(a, ReasoningSummaryDelta) and isinstance(b, ReasoningSummaryDelta):
        return ReasoningSummaryDelta(
            type="reasoning_summary",
            summary_index=a.summary_index,
            summary_delta=(a.summary_delta or "") + (b.summary_delta or ""),
        )
    if isinstance(a, ReasoningContentDelta) and isinstance(b, ReasoningContentDelta):
        return ReasoningContentDelta(
            type="reasoning_content",
            content_index=a.content_index,
            content_delta=(a.content_delta or "") + (b.content_delta or ""),
        )
    if isinstance(a, ToolRequestDelta) and isinstance(b, ToolRequestDelta):
        return ToolRequestDelta(
            type="tool_request",
            tool_call_id=a.tool_call_id,
            name=a.name,
            arguments_delta=(a.arguments_delta or "") + (b.arguments_delta or ""),
        )
    if isinstance(a, ToolResponseDelta) and isinstance(b, ToolResponseDelta):
        return ToolResponseDelta(
            type="tool_response",
            tool_call_id=a.tool_call_id,
            name=a.name,
            content_delta=(a.content_delta or "") + (b.content_delta or ""),
        )
    return b


def _merge_consecutive(updates: list[StreamTaskMessageDelta]) -> list[StreamTaskMessageDelta]:
    """Merge consecutive same-channel deltas. Order across channels is preserved exactly."""
    result: list[StreamTaskMessageDelta] = []
    for u in updates:
        if u.delta is None or not result:
            result.append(u)
            continue
        last = result[-1]
        if last.delta is not None and _can_merge(last.delta, u.delta):
            result[-1] = StreamTaskMessageDelta(
                parent_task_message=last.parent_task_message,
                delta=_merge_pair(last.delta, u.delta),
                type="delta",
            )
        else:
            result.append(u)
    return result


class CoalescingBuffer:
    """Time-and-size-windowed buffer that merges consecutive same-channel deltas.

    Decouples the producer (model event loop) from the publisher (Redis): ``add``
    only enqueues and may signal an early flush; the actual publish always runs
    on a background ticker, so the producer never awaits on a Redis round-trip.
    """

    FLUSH_INTERVAL_S = 0.050
    MAX_BUFFERED_CHARS = 128

    def __init__(self, on_flush: Callable[[StreamTaskMessageDelta], Awaitable[object]]):
        self._on_flush = on_flush
        self._buf: list[StreamTaskMessageDelta] = []
        self._buf_chars = 0
        self._first_flushed = False
        self._closed = False
        self._lock = asyncio.Lock()
        self._flush_signal = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run(), name="coalescing-buffer")

    async def add(self, update: StreamTaskMessageDelta) -> None:
        if self._closed:
            return
        async with self._lock:
            self._buf.append(update)
            self._buf_chars += _delta_char_len(update.delta)
            if not self._first_flushed or self._buf_chars >= self.MAX_BUFFERED_CHARS:
                self._first_flushed = True
                self._flush_signal.set()

    async def _run(self) -> None:
        try:
            while not self._closed:
                try:
                    await asyncio.wait_for(self._flush_signal.wait(), timeout=self.FLUSH_INTERVAL_S)
                except asyncio.TimeoutError:
                    pass
                async with self._lock:
                    self._flush_signal.clear()
                    drained = self._drain_locked()
                for u in drained:
                    try:
                        await self._on_flush(u)
                    except Exception as e:
                        logger.exception(f"CoalescingBuffer flush failed: {e}")
        except asyncio.CancelledError:
            pass

    async def close(self) -> None:
        self._closed = True
        if self._task is not None:
            self._flush_signal.set()
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        async with self._lock:
            drained = self._drain_locked()
        for u in drained:
            try:
                await self._on_flush(u)
            except Exception as e:
                logger.exception(f"CoalescingBuffer final flush failed: {e}")

    def _drain_locked(self) -> list[StreamTaskMessageDelta]:
        if not self._buf:
            return []
        merged = _merge_consecutive(self._buf)
        self._buf = []
        self._buf_chars = 0
        return merged


class DeltaAccumulator:
    def __init__(self):
        self._accumulated_deltas: list[TaskMessageDelta] = []
        self._delta_type: Literal["text", "data", "tool_request", "tool_response", "reasoning"] | None = None
        # For reasoning, we need to track both summary and content deltas
        self._reasoning_summaries: dict[int, str] = {}
        self._reasoning_contents: dict[int, str] = {}

    def add_delta(self, delta: TaskMessageDelta):
        if self._delta_type is None:
            if delta.type == "text":
                self._delta_type = "text"
            elif delta.type == "data":
                self._delta_type = "data"
            elif delta.type == "tool_request":
                self._delta_type = "tool_request"
            elif delta.type == "tool_response":
                self._delta_type = "tool_response"
            elif delta.type in ["reasoning_summary", "reasoning_content"]:
                self._delta_type = "reasoning"
            else:
                raise ValueError(f"Unknown delta type: {delta.type}")
        else:
            # For reasoning, we allow both summary and content deltas
            if self._delta_type == "reasoning":
                if delta.type not in ["reasoning_summary", "reasoning_content"]:
                    raise ValueError(
                        f"Expected reasoning delta but got: {delta.type}"
                    )
            elif self._delta_type != delta.type:
                raise ValueError(
                    f"Delta type mismatch: {self._delta_type} != {delta.type}"
                )

        # Handle reasoning deltas specially
        if delta.type == "reasoning_summary":
            if isinstance(delta, ReasoningSummaryDelta):
                if delta.summary_index not in self._reasoning_summaries:
                    self._reasoning_summaries[delta.summary_index] = ""
                self._reasoning_summaries[delta.summary_index] += delta.summary_delta or ""
        elif delta.type == "reasoning_content":
            if isinstance(delta, ReasoningContentDelta):
                if delta.content_index not in self._reasoning_contents:
                    self._reasoning_contents[delta.content_index] = ""
                self._reasoning_contents[delta.content_index] += delta.content_delta or ""
        else:
            self._accumulated_deltas.append(delta)

    def convert_to_content(self) -> TaskMessageContent:
        if self._delta_type == "text":
            # Type assertion: we know all deltas are TextDelta when _delta_type is TEXT
            text_deltas = [delta for delta in self._accumulated_deltas if isinstance(delta, TextDelta)]
            text_content_str = "".join(
                [delta.text_delta or "" for delta in text_deltas]
            )
            return TextContent(
                author="agent",
                content=text_content_str,
            )
        elif self._delta_type == "data":
            # Type assertion: we know all deltas are DataDelta when _delta_type is DATA
            data_deltas = [delta for delta in self._accumulated_deltas if isinstance(delta, DataDelta)]
            data_content_str = "".join(
                [delta.data_delta or "" for delta in data_deltas]
            )
            try:
                data = json.loads(data_content_str)
            except json.JSONDecodeError as e:
                raise ValueError(
                    f"Accumulated data content is not valid JSON: {data_content_str}"
                ) from e
            return DataContent(
                author="agent",
                data=data,
            )
        elif self._delta_type == "tool_request":
            # Type assertion: we know all deltas are ToolRequestDelta when _delta_type is TOOL_REQUEST
            tool_request_deltas = [delta for delta in self._accumulated_deltas if isinstance(delta, ToolRequestDelta)]
            arguments_content_str = "".join(
                [delta.arguments_delta or "" for delta in tool_request_deltas]
            )
            try:
                arguments = json.loads(arguments_content_str)
            except json.JSONDecodeError as e:
                raise ValueError(
                    f"Accumulated tool request arguments is not valid JSON: {arguments_content_str}"
                ) from e
            return ToolRequestContent(
                author="agent",
                tool_call_id=tool_request_deltas[0].tool_call_id,
                name=tool_request_deltas[0].name,
                arguments=arguments,
            )
        elif self._delta_type == "tool_response":
            # Type assertion: we know all deltas are ToolResponseDelta when _delta_type is TOOL_RESPONSE
            tool_response_deltas = [delta for delta in self._accumulated_deltas if isinstance(delta, ToolResponseDelta)]
            tool_response_content_str = "".join(
                [delta.content_delta or "" for delta in tool_response_deltas]
            )
            return ToolResponseContent(
                author="agent",
                tool_call_id=tool_response_deltas[0].tool_call_id,
                name=tool_response_deltas[0].name,
                content=tool_response_content_str,
            )
        elif self._delta_type == "reasoning":
            # Convert accumulated reasoning deltas to ReasoningContent
            # Sort by index to maintain order
            summary_list = [self._reasoning_summaries[i] for i in sorted(self._reasoning_summaries.keys()) if self._reasoning_summaries[i]]
            content_list = [self._reasoning_contents[i] for i in sorted(self._reasoning_contents.keys()) if self._reasoning_contents[i]]
            
            # Only return reasoning content if we have non-empty summaries or content
            if summary_list or content_list:
                return ReasoningContent(
                    author="agent",
                    summary=summary_list,
                    content=content_list if content_list else None,
                    type="reasoning",
                    style="static",
                )
            else:
                # Return empty text content instead of empty reasoning
                return TextContent(
                    author="agent",
                    content="",
                )
        else:
            raise ValueError(f"Unknown delta type: {self._delta_type}")


class StreamingTaskMessageContext:
    def __init__(
        self,
        task_id: str,
        initial_content: TaskMessageContent,
        agentex_client: AsyncAgentex,
        streaming_service: "StreamingService",
        streaming_mode: StreamingMode = "coalesced",
    ):
        self.task_id = task_id
        self.initial_content = initial_content
        self.task_message: TaskMessage | None = None
        self._agentex_client = agentex_client
        self._streaming_service = streaming_service
        self._is_closed = False
        self._delta_accumulator = DeltaAccumulator()
        self._streaming_mode: StreamingMode = streaming_mode
        self._buffer: CoalescingBuffer | None = None

    async def __aenter__(self) -> "StreamingTaskMessageContext":
        return await self.open()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return await self.close()

    async def open(self) -> "StreamingTaskMessageContext":
        self._is_closed = False

        self.task_message = await self._agentex_client.messages.create(
            task_id=self.task_id,
            content=self.initial_content.model_dump(),
            streaming_status="IN_PROGRESS",
        )

        # Send the START event
        start_event = StreamTaskMessageStart(
            parent_task_message=self.task_message,
            content=self.initial_content,
            type="start",
        )
        await self._streaming_service.stream_update(start_event)

        if self._streaming_mode == "coalesced":
            self._buffer = CoalescingBuffer(on_flush=self._streaming_service.stream_update)
            self._buffer.start()

        return self

    async def close(self) -> TaskMessage:
        """Close the streaming context."""
        if not self.task_message:
            raise ValueError("Context not properly initialized - no task message")

        if self._is_closed:
            return self.task_message  # Already done

        # Drain any buffered deltas before announcing DONE so consumers see the
        # full sequence in order.
        if self._buffer is not None:
            await self._buffer.close()
            self._buffer = None

        # Send the DONE event
        done_event = StreamTaskMessageDone(
            parent_task_message=self.task_message,
            type="done",
        )
        await self._streaming_service.stream_update(done_event)

        # Update the task message with the final content
        has_deltas = (
            self._delta_accumulator._accumulated_deltas or
            self._delta_accumulator._reasoning_summaries or
            self._delta_accumulator._reasoning_contents
        )
        if has_deltas:
            self.task_message.content = self._delta_accumulator.convert_to_content()

        await self._agentex_client.messages.update(
            task_id=self.task_id,
            message_id=self.task_message.id,
            content=self.task_message.content.model_dump(),
            streaming_status="DONE",
        )

        # Mark the context as done
        self._is_closed = True
        return self.task_message

    async def stream_update(
        self, update: TaskMessageUpdate
    ) -> TaskMessageUpdate | None:
        """Stream an update to the repository.

        Behavior depends on the context's ``streaming_mode``:
        - "off": delta updates feed the accumulator (so the persisted message
          body is correct) but are never published.
        - "per_token": delta updates are published immediately.
        - "coalesced": delta updates are queued in a 50ms / 128-char window and
          flushed as merged batches on a background ticker; the first delta
          flushes immediately for fast perceived responsiveness.

        ``StreamTaskMessageDone`` and ``StreamTaskMessageFull`` updates always
        publish synchronously regardless of mode so consumers and persistence
        stay in sync.
        """
        if self._is_closed:
            raise ValueError("Context is already done")

        if not self.task_message:
            raise ValueError("Context not properly initialized - no task message")

        if isinstance(update, StreamTaskMessageDelta):
            if update.delta is not None:
                self._delta_accumulator.add_delta(update.delta)
            if self._streaming_mode == "off":
                return update
            if self._streaming_mode == "coalesced" and self._buffer is not None:
                await self._buffer.add(update)
                return update

        result = await self._streaming_service.stream_update(update)

        if isinstance(update, StreamTaskMessageDone):
            await self.close()
            return update
        elif isinstance(update, StreamTaskMessageFull):
            await self._agentex_client.messages.update(
                task_id=self.task_id,
                message_id=update.parent_task_message.id,  # type: ignore[union-attr]
                content=update.content.model_dump(),
                streaming_status="DONE",
            )
            self._is_closed = True
        return result


class StreamingService:
    def __init__(
        self,
        agentex_client: AsyncAgentex,
        stream_repository: StreamRepository,
    ):
        self._agentex_client = agentex_client
        self._stream_repository = stream_repository

    def streaming_task_message_context(
        self,
        task_id: str,
        initial_content: TaskMessageContent,
        streaming_mode: StreamingMode = "coalesced",
    ) -> StreamingTaskMessageContext:
        return StreamingTaskMessageContext(
            task_id=task_id,
            initial_content=initial_content,
            agentex_client=self._agentex_client,
            streaming_service=self,
            streaming_mode=streaming_mode,
        )

    async def stream_update(
        self, update: TaskMessageUpdate
    ) -> TaskMessageUpdate | None:
        """
        Stream an update to the repository.

        Args:
            update: The update to stream

        Returns:
            True if event was streamed successfully, False otherwise
        """
        stream_topic = _get_stream_topic(update.parent_task_message.task_id)  # type: ignore[union-attr]

        try:
            await self._stream_repository.send_event(
                topic=stream_topic, event=update.model_dump(mode="json")  # type: ignore
            )
            return update
        except Exception as e:
            logger.exception(f"Failed to stream event: {e}")
            return None
