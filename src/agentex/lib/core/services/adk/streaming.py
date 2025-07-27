import json
from typing import Literal, cast

from agentex import AsyncAgentex
from agentex.lib.core.adapters.streams.port import StreamRepository
from agentex.lib.types.task_message_updates import (
    TaskMessageDelta, 
    TaskMessageUpdate,
    TextDelta,
    DataDelta,
    ToolRequestDelta,
    ToolResponseDelta,
    StreamTaskMessage,
    StreamTaskMessageStart,
    StreamTaskMessageDelta,
    StreamTaskMessageFull,
    StreamTaskMessageDone,
)
from agentex.lib.utils.logging import make_logger
from agentex.types.data_content import DataContent
from agentex.types.task_message import (
    TaskMessage,
    TaskMessageContent,
)
from agentex.types.text_content import TextContent
from agentex.types.tool_request_content import ToolRequestContent
from agentex.types.tool_response_content import ToolResponseContent

logger = make_logger(__name__)


def _get_stream_topic(task_id: str) -> str:
    return f"task:{task_id}"


class DeltaAccumulator:
    def __init__(self):
        self._accumulated_deltas: list[TaskMessageDelta] = []
        self._delta_type: Literal["text", "data", "tool_request", "tool_response"] | None = None

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
            else:
                raise ValueError(f"Unknown delta type: {delta.type}")
        else:
            if self._delta_type != delta.type:
                raise ValueError(
                    f"Delta type mismatch: {self._delta_type} != {delta.type}"
                )

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
                [delta.tool_response_delta or "" for delta in tool_response_deltas]
            )
            return ToolResponseContent(
                author="agent",
                tool_call_id=tool_response_deltas[0].tool_call_id,
                name=tool_response_deltas[0].name,
                content=tool_response_content_str,
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
        done_event = StreamTaskMessageDone(parent_task_message=self.task_message)
        await self._streaming_service.stream_update(done_event)

        # Update the task message with the final content
        if self._delta_accumulator._accumulated_deltas:
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
        self, update: StreamTaskMessage
    ) -> StreamTaskMessage | None:
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
                message_id=update.parent_task_message.id,
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
        stream_topic = _get_stream_topic(update.parent_task_message.task_id)

        try:
            await self._stream_repository.send_event(
                topic=stream_topic, event=update.model_dump(mode="json")  # type: ignore
            )
            return update
        except Exception as e:
            logger.exception(f"Failed to stream event: {e}")
            return None
