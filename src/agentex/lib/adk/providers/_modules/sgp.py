from datetime import timedelta
from typing import AsyncGenerator

from agentex.lib.adk.utils._modules.client import create_async_agentex_client
from scale_gp import SGPClient, SGPClientError
from temporalio.common import RetryPolicy

from agentex import AsyncAgentex
from agentex.lib.core.adapters.llm.adapter_sgp import SGPLLMGateway
from agentex.lib.core.adapters.streams.adapter_redis import RedisStreamRepository
from agentex.lib.core.services.adk.providers.litellm import LiteLLMService
from agentex.lib.core.services.adk.providers.sgp import SGPService
from agentex.lib.core.services.adk.streaming import StreamingService
from agentex.lib.core.temporal.activities.activity_helpers import ActivityHelpers
from agentex.lib.core.temporal.activities.adk.providers.litellm_activities import ChatCompletionParams, \
    LiteLLMActivityName, ChatCompletionAutoSendParams, ChatCompletionStreamAutoSendParams
from agentex.lib.core.temporal.activities.adk.providers.sgp_activities import (
    DownloadFileParams,
    FileContentResponse,
    SGPActivityName,
)
from agentex.lib.core.tracing.tracer import AsyncTracer
from agentex.lib.types.llm_messages import LLMConfig, Completion
from agentex.lib.utils.logging import make_logger
from agentex.lib.utils.temporal import in_temporal_workflow
from agentex.types import TaskMessage

logger = make_logger(__name__)

DEFAULT_RETRY_POLICY = RetryPolicy(maximum_attempts=1)


class SGPModule:
    """
    Module for managing SGP agent operations in Agentex.
    Provides high-level methods for chat completion, streaming, agentic streaming, and message classification.
    """

    def __init__(
        self,
        sgp_service: SGPService | None = None,
        litellm_service: LiteLLMService | None = None,
    ):
        if sgp_service is None:
            try:
                sgp_client = SGPClient()
                agentex_client = create_async_agentex_client()
                tracer = AsyncTracer(agentex_client)
                self._sgp_service = SGPService(sgp_client=sgp_client, tracer=tracer)
            except SGPClientError:
                self._sgp_service = None
        else:
            self._sgp_service = sgp_service

        agentex_client = create_async_agentex_client()
        stream_repository = RedisStreamRepository()
        streaming_service = StreamingService(
            agentex_client=agentex_client,
            stream_repository=stream_repository,
        )
        litellm_gateway = SGPLLMGateway()
        tracer = AsyncTracer(agentex_client)
        self._litellm_service = LiteLLMService(
            agentex_client=agentex_client,
            llm_gateway=litellm_gateway,
            streaming_service=streaming_service,
            tracer=tracer,
        )

    async def download_file_content(
        self,
        params: DownloadFileParams,
        start_to_close_timeout: timedelta = timedelta(seconds=30),
        heartbeat_timeout: timedelta = timedelta(seconds=30),
        retry_policy: RetryPolicy = DEFAULT_RETRY_POLICY,
    ) -> FileContentResponse:
        """
        Download the content of a file from SGP.

        Args:
            params (DownloadFileParams): The parameters for the download file content activity.
            start_to_close_timeout (timedelta): The start to close timeout.
            heartbeat_timeout (timedelta): The heartbeat timeout.
            retry_policy (RetryPolicy): The retry policy.

        Returns:
            FileContentResponse: The content of the file
        """
        if self._sgp_service is None:
            raise ValueError(
                "SGP activities are disabled because the SGP client could not be initialized. Please check that the SGP_API_KEY environment variable is set."
            )

        params = DownloadFileParams(
            file_id=params.file_id,
            filename=params.filename,
        )
        if in_temporal_workflow():
            return await ActivityHelpers.execute_activity(
                activity_name=SGPActivityName.DOWNLOAD_FILE_CONTENT,
                request=params,
                response_type=FileContentResponse,
                start_to_close_timeout=start_to_close_timeout,
                heartbeat_timeout=heartbeat_timeout,
                retry_policy=retry_policy,
            )
        else:
            return await self._sgp_service.download_file_content(
                file_id=params.file_id,
                filename=params.filename,
            )

    async def chat_completion(
        self,
        llm_config: LLMConfig,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
        start_to_close_timeout: timedelta = timedelta(seconds=120),
        heartbeat_timeout: timedelta = timedelta(seconds=120),
        retry_policy: RetryPolicy = DEFAULT_RETRY_POLICY,
    ) -> Completion:
        """
        Perform a chat completion using LiteLLM.

        Args:
            llm_config (LLMConfig): The configuration for the LLM.
            trace_id (Optional[str]): The trace ID for tracing.
            parent_span_id (Optional[str]): The parent span ID for tracing.
            start_to_close_timeout (timedelta): The start to close timeout.
            heartbeat_timeout (timedelta): The heartbeat timeout.
            retry_policy (RetryPolicy): The retry policy.

        Returns:
            Completion: An OpenAI compatible Completion object
        """
        if in_temporal_workflow():
            params = ChatCompletionParams(
                trace_id=trace_id, parent_span_id=parent_span_id, llm_config=llm_config
            )
            return await ActivityHelpers.execute_activity(
                activity_name=LiteLLMActivityName.CHAT_COMPLETION,
                request=params,
                response_type=Completion,
                start_to_close_timeout=start_to_close_timeout,
                heartbeat_timeout=heartbeat_timeout,
                retry_policy=retry_policy,
            )
        else:
            return await self._litellm_service.chat_completion(
                llm_config=llm_config,
                trace_id=trace_id,
                parent_span_id=parent_span_id,
            )

    async def chat_completion_auto_send(
        self,
        task_id: str,
        llm_config: LLMConfig,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
        start_to_close_timeout: timedelta = timedelta(seconds=120),
        heartbeat_timeout: timedelta = timedelta(seconds=120),
        retry_policy: RetryPolicy = DEFAULT_RETRY_POLICY,
    ) -> TaskMessage | None:
        """
        Chat completion with automatic TaskMessage creation.

        Args:
            task_id (str): The ID of the task.
            llm_config (LLMConfig): The configuration for the LLM (must have stream=False).
            trace_id (Optional[str]): The trace ID for tracing.
            parent_span_id (Optional[str]): The parent span ID for tracing.
            start_to_close_timeout (timedelta): The start to close timeout.
            heartbeat_timeout (timedelta): The heartbeat timeout.
            retry_policy (RetryPolicy): The retry policy.

        Returns:
            TaskMessage: The final TaskMessage
        """
        if in_temporal_workflow():
            # Use streaming activity with stream=False for non-streaming auto-send
            params = ChatCompletionAutoSendParams(
                trace_id=trace_id,
                parent_span_id=parent_span_id,
                task_id=task_id,
                llm_config=llm_config,
            )
            return await ActivityHelpers.execute_activity(
                activity_name=LiteLLMActivityName.CHAT_COMPLETION_AUTO_SEND,
                request=params,
                response_type=TaskMessage,
                start_to_close_timeout=start_to_close_timeout,
                heartbeat_timeout=heartbeat_timeout,
                retry_policy=retry_policy,
            )
        else:
            return await self._litellm_service.chat_completion_auto_send(
                task_id=task_id,
                llm_config=llm_config,
                trace_id=trace_id,
                parent_span_id=parent_span_id,
            )

    async def chat_completion_stream(
        self,
        llm_config: LLMConfig,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
    ) -> AsyncGenerator[Completion, None]:
        """
        Stream chat completion chunks using LiteLLM.

        DEFAULT: Returns raw streaming chunks for manual handling.

        NOTE: This method does NOT work in Temporal workflows!
        Temporal activities cannot return generators. Use chat_completion_stream_auto_send() instead.

        Args:
            llm_config (LLMConfig): The configuration for the LLM (must have stream=True).
            trace_id (Optional[str]): The trace ID for tracing.
            parent_span_id (Optional[str]): The parent span ID for tracing.
            start_to_close_timeout (timedelta): The start to close timeout.
            heartbeat_timeout (timedelta): The heartbeat timeout.
            retry_policy (RetryPolicy): The retry policy.

        Returns:
            AsyncGenerator[Completion, None]: Generator yielding completion chunks

        Raises:
            ValueError: If called from within a Temporal workflow
        """
        # Delegate to service - it handles temporal workflow checks
        async for chunk in self._litellm_service.chat_completion_stream(
            llm_config=llm_config,
            trace_id=trace_id,
            parent_span_id=parent_span_id,
        ):
            yield chunk

    async def chat_completion_stream_auto_send(
        self,
        task_id: str,
        llm_config: LLMConfig,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
        start_to_close_timeout: timedelta = timedelta(seconds=120),
        heartbeat_timeout: timedelta = timedelta(seconds=120),
        retry_policy: RetryPolicy = DEFAULT_RETRY_POLICY,
    ) -> TaskMessage | None:
        """
        Stream chat completion with automatic TaskMessage creation and streaming.

        Args:
            task_id (str): The ID of the task to run the agent for.
            llm_config (LLMConfig): The configuration for the LLM (must have stream=True).
            trace_id (Optional[str]): The trace ID for tracing.
            parent_span_id (Optional[str]): The parent span ID for tracing.
            start_to_close_timeout (timedelta): The start to close timeout.
            heartbeat_timeout (timedelta): The heartbeat timeout.
            retry_policy (RetryPolicy): The retry policy.

        Returns:
            TaskMessage: The final TaskMessage after streaming is complete
        """
        if in_temporal_workflow():
            params = ChatCompletionStreamAutoSendParams(
                trace_id=trace_id,
                parent_span_id=parent_span_id,
                task_id=task_id,
                llm_config=llm_config,
            )
            return await ActivityHelpers.execute_activity(
                activity_name=LiteLLMActivityName.CHAT_COMPLETION_STREAM_AUTO_SEND,
                request=params,
                response_type=TaskMessage,
                start_to_close_timeout=start_to_close_timeout,
                heartbeat_timeout=heartbeat_timeout,
                retry_policy=retry_policy,
            )
        else:
            return await self._litellm_service.chat_completion_stream_auto_send(
                task_id=task_id,
                llm_config=llm_config,
                trace_id=trace_id,
                parent_span_id=parent_span_id,
            )