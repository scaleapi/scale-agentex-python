from collections.abc import AsyncGenerator

from agentex import AsyncAgentex
from agentex.lib.core.adapters.llm.adapter_litellm import LiteLLMGateway
from agentex.lib.core.services.adk.streaming import StreamingService
from agentex.lib.core.tracing.tracer import AsyncTracer
from agentex.lib.types.llm_messages import (
    Completion,
    LLMConfig,
)
from agentex.lib.types.task_message_updates import (
    StreamTaskMessageDelta,
    StreamTaskMessageFull,
    TextDelta,
)
from agentex.types.task_message import TaskMessage
from agentex.types.task_message_content import TextContent
from agentex.lib.utils import logging
from agentex.lib.utils.completions import concat_completion_chunks
from agentex.lib.utils.temporal import heartbeat_if_in_workflow

logger = logging.make_logger(__name__)


class LiteLLMService:
    def __init__(
        self,
        agentex_client: AsyncAgentex,
        streaming_service: StreamingService,
        tracer: AsyncTracer,
        llm_gateway: LiteLLMGateway | None = None,
    ):
        self.agentex_client = agentex_client
        self.llm_gateway = llm_gateway
        self.streaming_service = streaming_service
        self.tracer = tracer

    async def chat_completion(
        self,
        llm_config: LLMConfig,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
    ) -> Completion:
        trace = self.tracer.trace(trace_id)
        async with trace.span(
            parent_id=parent_span_id,
            name="chat_completion",
            input=llm_config.model_dump(),
        ) as span:
            heartbeat_if_in_workflow("chat completion")
            if self.llm_gateway is None:
                raise ValueError("LLM Gateway is not set")
            completion = await self.llm_gateway.acompletion(**llm_config.model_dump())
            if span:
                span.output = completion.model_dump()
            return completion

    async def chat_completion_auto_send(
        self,
        task_id: str,
        llm_config: LLMConfig,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
    ) -> TaskMessage | None:
        """
        Chat completion with automatic TaskMessage creation. This does not stream the completion. To stream use chat_completion_stream_auto_send.

        Args:
            task_id (str): The ID of the task to run the agent for.
            llm_config (LLMConfig): The configuration for the LLM (must have stream=True).

        Returns:
            TaskMessage: A TaskMessage object
        """

        if llm_config.stream:
            raise ValueError(
                "LLM config must not have stream=True. To stream use `chat_completion_stream` or `chat_completion_stream_auto_send`."
            )

        if self.llm_gateway is None:
            raise ValueError("LLM Gateway is not set")

        trace = self.tracer.trace(trace_id)
        async with trace.span(
            parent_id=parent_span_id,
            name="chat_completion_auto_send",
            input=llm_config.model_dump(),
        ) as span:
            heartbeat_if_in_workflow("chat completion auto send")

            async with self.streaming_service.streaming_task_message_context(
                task_id=task_id,
                initial_content=TextContent(
                    author="agent",
                    content="",
                    format="markdown",
                ),
            ) as streaming_context:
                completion = await self.llm_gateway.acompletion(**llm_config.model_dump())
                if (
                    completion.choices
                    and len(completion.choices) > 0
                    and completion.choices[0].message
                ):
                    final_content = TextContent(
                        author="agent",
                        content=completion.choices[0].message.content or "",
                        format="markdown",
                    )
                    await streaming_context.stream_update(
                        update=StreamTaskMessageFull(
                            parent_task_message=streaming_context.task_message,
                            content=final_content,
                        ),
                    )
                else:
                    raise ValueError("No completion message returned from LLM")

            if span:
                if streaming_context.task_message:
                    span.output = streaming_context.task_message.model_dump()
            return streaming_context.task_message if streaming_context.task_message else None

    async def chat_completion_stream(
        self,
        llm_config: LLMConfig,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
    ) -> AsyncGenerator[Completion, None]:
        """
        Stream chat completion chunks using LiteLLM.

        Args:
            llm_config (LLMConfig): The configuration for the LLM (must have stream=True).
            trace_id (Optional[str]): The trace ID for tracing.
            parent_span_id (Optional[str]): The parent span ID for tracing.

        Returns:
            AsyncGenerator[Completion, None]: Generator yielding completion chunks

        Raises:
            ValueError: If called from within a Temporal workflow or if stream=False
        """
        if not llm_config.stream:
            raise ValueError("LLM config must have stream=True for streaming")

        if self.llm_gateway is None:
            raise ValueError("LLM Gateway is not set")

        trace = self.tracer.trace(trace_id)
        async with trace.span(
            parent_id=parent_span_id,
            name="chat_completion_stream",
            input=llm_config.model_dump(),
        ) as span:
            # Direct streaming outside temporal - yield each chunk as it comes
            chunks: list[Completion] = []
            async for chunk in self.llm_gateway.acompletion_stream(
                **llm_config.model_dump()
            ):
                chunks.append(chunk)
                yield chunk
            if span:
                span.output = concat_completion_chunks(chunks).model_dump()

    async def chat_completion_stream_auto_send(
        self,
        task_id: str,
        llm_config: LLMConfig,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
    ) -> TaskMessage | None:
        """
        Stream chat completion with automatic TaskMessage creation and streaming.

        Args:
            task_id (str): The ID of the task to run the agent for.
            llm_config (LLMConfig): The configuration for the LLM (must have stream=True).

        Returns:
            TaskMessage: A TaskMessage object
        """
        heartbeat_if_in_workflow("chat completion stream")

        if self.llm_gateway is None:
            raise ValueError("LLM Gateway is not set")

        if not llm_config.stream:
            llm_config.stream = True

        trace = self.tracer.trace(trace_id)
        async with trace.span(
            parent_id=parent_span_id,
            name="chat_completion_stream",
            input=llm_config.model_dump(),
        ) as span:
            # Use streaming context manager
            async with self.streaming_service.streaming_task_message_context(
                task_id=task_id,
                initial_content=TextContent(
                    author="agent",
                    content="",
                    format="markdown",
                ),
            ) as streaming_context:
                # Get the streaming response
                chunks = []
                async for response in self.llm_gateway.acompletion_stream(
                    **llm_config.model_dump()
                ):
                    heartbeat_if_in_workflow("chat completion streaming")
                    if (
                        response.choices
                        and len(response.choices) > 0
                        and response.choices[0].delta
                    ):
                        delta = response.choices[0].delta.content
                        if delta:
                            # Stream the chunk via the context manager
                            await streaming_context.stream_update(
                                update=StreamTaskMessageDelta(
                                    parent_task_message=streaming_context.task_message,
                                    delta=TextDelta(text_delta=delta),
                                ),
                            )
                            heartbeat_if_in_workflow("content chunk streamed")

                        # Store the chunk for final message assembly
                        chunks.append(response)

                # Update the final message content
                complete_message = concat_completion_chunks(chunks)
                if (
                    complete_message
                    and complete_message.choices
                    and complete_message.choices[0].message
                ):
                    final_content = TextContent(
                        author="agent",
                        content=complete_message.choices[0].message.content or "",
                    )
                    await streaming_context.stream_update(
                        update=StreamTaskMessageFull(
                            parent_task_message=streaming_context.task_message,
                            content=final_content,
                        ),
                    )

                heartbeat_if_in_workflow("chat completion stream complete")

            if span:
                if streaming_context.task_message:
                    span.output = streaming_context.task_message.model_dump()

        return streaming_context.task_message if streaming_context.task_message else None
