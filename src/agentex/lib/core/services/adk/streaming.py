from __future__ import annotations

import json
from typing import Literal

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
    ):
        self.task_id = task_id
        self.initial_content = initial_content
        self.task_message: TaskMessage | None = None
        self._agentex_client = agentex_client
        self._streaming_service = streaming_service
        self._is_closed = False
        self._delta_accumulator = DeltaAccumulator()

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

        return self

    async def close(self) -> TaskMessage:
        """Close the streaming context."""
        if not self.task_message:
            raise ValueError("Context not properly initialized - no task message")

        if self._is_closed:
            return self.task_message  # Already done

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
        """Stream an update to the repository."""
        if self._is_closed:
            raise ValueError("Context is already done")

        if not self.task_message:
            raise ValueError("Context not properly initialized - no task message")

        if isinstance(update, StreamTaskMessageDelta):
            if update.delta is not None:
                self._delta_accumulator.add_delta(update.delta)

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
    ) -> StreamingTaskMessageContext:
        return StreamingTaskMessageContext(
            task_id=task_id,
            initial_content=initial_content,
            agentex_client=self._agentex_client,
            streaming_service=self,
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
