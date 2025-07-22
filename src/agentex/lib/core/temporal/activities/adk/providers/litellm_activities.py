from enum import Enum

from temporalio import activity

from agentex.lib.core.services.adk.providers.litellm import LiteLLMService
from agentex.lib.types.llm_messages import Completion, LLMConfig
from agentex.types.task_message import TaskMessage
from agentex.lib.types.tracing import BaseModelWithTraceParams
from agentex.lib.utils import logging

logger = logging.make_logger(__name__)


class LiteLLMActivityName(str, Enum):
    CHAT_COMPLETION = "chat-completion"
    CHAT_COMPLETION_AUTO_SEND = "chat-completion-auto-send"
    # Note: CHAT_COMPLETION_STREAM is not supported in Temporal due to generator limitations
    CHAT_COMPLETION_STREAM_AUTO_SEND = "chat-completion-stream-auto-send"


class ChatCompletionParams(BaseModelWithTraceParams):
    llm_config: LLMConfig


class ChatCompletionAutoSendParams(BaseModelWithTraceParams):
    task_id: str
    llm_config: LLMConfig


class ChatCompletionStreamAutoSendParams(BaseModelWithTraceParams):
    task_id: str
    llm_config: LLMConfig


class LiteLLMActivities:
    def __init__(self, litellm_service: LiteLLMService):
        self._litellm_service = litellm_service

    @activity.defn(name=LiteLLMActivityName.CHAT_COMPLETION)
    async def chat_completion(self, params: ChatCompletionParams) -> Completion:
        return await self._litellm_service.chat_completion(
            llm_config=params.llm_config,
            trace_id=params.trace_id,
            parent_span_id=params.parent_span_id,
        )

    @activity.defn(name=LiteLLMActivityName.CHAT_COMPLETION_AUTO_SEND)
    async def chat_completion_auto_send(self, params: ChatCompletionAutoSendParams) -> TaskMessage | None:
        """
        Activity for non-streaming chat completion with automatic TaskMessage creation.
        """
        return await self._litellm_service.chat_completion_auto_send(
            task_id=params.task_id,
            llm_config=params.llm_config,
            trace_id=params.trace_id,
            parent_span_id=params.parent_span_id,
        )

    @activity.defn(name=LiteLLMActivityName.CHAT_COMPLETION_STREAM_AUTO_SEND)
    async def chat_completion_stream_auto_send(
        self, params: ChatCompletionStreamAutoSendParams
    ) -> TaskMessage | None:
        """
        Activity for streaming chat completion with automatic TaskMessage creation.
        """
        return await self._litellm_service.chat_completion_stream_auto_send(
            task_id=params.task_id,
            llm_config=params.llm_config,
            trace_id=params.trace_id,
            parent_span_id=params.parent_span_id,
        )
