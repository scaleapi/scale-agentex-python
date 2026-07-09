"""Tests that LiteLLMService puts LLM token usage on spans for billing.

Covers the paths that previously dropped usage: both auto_send variants (span
output was only the TaskMessage dump) and streaming (litellm omits usage unless
``stream_options.include_usage`` is set).
"""

from __future__ import annotations

from datetime import UTC, datetime
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

from agentex.types.span import Span
from agentex.types.task_message import TaskMessage
from agentex.types.task_message_content import TextContent
from agentex.lib.types.llm_messages import (
    Delta,
    Usage,
    Choice,
    LLMConfig,
    Completion,
    AssistantMessage,
)
from agentex.lib.core.services.adk.providers.litellm import (
    LiteLLMService,
    _stream_kwargs_with_usage,
)


class FakeTrace:
    def __init__(self) -> None:
        self.spans: list[Span] = []

    @asynccontextmanager
    async def span(self, name, parent_id=None, input=None, data=None, task_id=None):
        span = Span(
            id=f"span-{len(self.spans)}",
            name=name,
            start_time=datetime.now(UTC),
            trace_id="trace-1",
            parent_id=parent_id,
            input=input,
        )
        self.spans.append(span)
        yield span


class FakeTracer:
    def __init__(self) -> None:
        self.trace_obj = FakeTrace()

    def trace(self, trace_id):
        return self.trace_obj


def _make_streaming_service():
    streaming_context = MagicMock()
    streaming_context.task_message = TaskMessage(
        id="msg-1",
        task_id="task-1",
        content=TextContent(author="agent", content="", format="markdown"),
    )
    streaming_context.stream_update = AsyncMock()

    @asynccontextmanager
    async def fake_context(**kwargs):
        yield streaming_context

    streaming_service = MagicMock()
    streaming_service.streaming_task_message_context = fake_context
    return streaming_service, streaming_context


def _make_service(llm_gateway) -> tuple[LiteLLMService, FakeTracer]:
    streaming_service, _ = _make_streaming_service()
    tracer = FakeTracer()
    service = LiteLLMService(
        agentex_client=MagicMock(),
        streaming_service=streaming_service,
        tracer=tracer,
        llm_gateway=llm_gateway,
    )
    return service, tracer


def _stream_gateway(chunks, captured_kwargs):
    gateway = MagicMock()

    def acompletion_stream(**kwargs):
        captured_kwargs.update(kwargs)

        async def stream():
            for chunk in chunks:
                yield chunk

        return stream()

    gateway.acompletion_stream = acompletion_stream
    return gateway


def _delta_chunk(content: str, role: str | None = None) -> Completion:
    return Completion(choices=[Choice(index=0, delta=Delta(content=content, role=role))])


def _usage_only_chunk() -> Completion:
    return Completion(
        choices=[],
        usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
    )


class TestStreamKwargsWithUsage:
    def test_defaults_include_usage_on(self):
        config = LLMConfig(model="gpt-4o", messages=[], stream=True)
        assert _stream_kwargs_with_usage(config)["stream_options"] == {"include_usage": True}

    def test_caller_opt_out_preserved(self):
        config = LLMConfig(model="gpt-4o", messages=[], stream=True, stream_options={"include_usage": False})
        assert _stream_kwargs_with_usage(config)["stream_options"] == {"include_usage": False}

    def test_merges_with_other_stream_options(self):
        config = LLMConfig(model="gpt-4o", messages=[], stream=True, stream_options={"other": 1})
        assert _stream_kwargs_with_usage(config)["stream_options"] == {"include_usage": True, "other": 1}


class TestChatCompletionAutoSend:
    async def test_span_output_carries_usage(self):
        completion = Completion(
            choices=[Choice(index=0, message=AssistantMessage(content="Hello!"), finish_reason="stop")],
            usage=Usage(prompt_tokens=7, completion_tokens=3, total_tokens=10),
        )
        gateway = MagicMock()
        gateway.acompletion = AsyncMock(return_value=completion)
        service, tracer = _make_service(gateway)

        await service.chat_completion_auto_send(
            task_id="task-1",
            llm_config=LLMConfig(model="gpt-4o", messages=[], stream=False),
            trace_id="trace-1",
        )

        span = tracer.trace_obj.spans[0]
        assert span.output["usage"] == {"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10}

    async def test_span_output_omits_usage_when_absent(self):
        completion = Completion(
            choices=[Choice(index=0, message=AssistantMessage(content="Hello!"), finish_reason="stop")],
        )
        gateway = MagicMock()
        gateway.acompletion = AsyncMock(return_value=completion)
        service, tracer = _make_service(gateway)

        await service.chat_completion_auto_send(
            task_id="task-1",
            llm_config=LLMConfig(model="gpt-4o", messages=[], stream=False),
            trace_id="trace-1",
        )

        assert "usage" not in tracer.trace_obj.spans[0].output


class TestChatCompletionStream:
    async def test_stream_requests_usage_and_span_output_carries_it(self):
        captured_kwargs: dict = {}
        chunks = [_delta_chunk("Hel", role="assistant"), _delta_chunk("lo!"), _usage_only_chunk()]
        service, tracer = _make_service(_stream_gateway(chunks, captured_kwargs))

        results = []
        async for chunk in service.chat_completion_stream(
            llm_config=LLMConfig(model="gpt-4o", messages=[], stream=True),
            trace_id="trace-1",
        ):
            results.append(chunk)

        assert len(results) == 3
        assert captured_kwargs["stream_options"] == {"include_usage": True}
        span = tracer.trace_obj.spans[0]
        assert span.output["usage"] == {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        assert span.output["choices"][0]["message"]["content"] == "Hello!"


class TestChatCompletionStreamAutoSend:
    async def test_usage_only_final_chunk_reaches_span_output(self):
        captured_kwargs: dict = {}
        chunks = [_delta_chunk("Hel", role="assistant"), _delta_chunk("lo!"), _usage_only_chunk()]
        service, tracer = _make_service(_stream_gateway(chunks, captured_kwargs))

        await service.chat_completion_stream_auto_send(
            task_id="task-1",
            llm_config=LLMConfig(model="gpt-4o", messages=[], stream=True),
            trace_id="trace-1",
        )

        assert captured_kwargs["stream_options"] == {"include_usage": True}
        span = tracer.trace_obj.spans[0]
        assert span.output["usage"] == {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        # TaskMessage dump is still the base of the span output
        assert span.output["id"] == "msg-1"

    async def test_stream_without_usage_chunk_omits_usage(self):
        captured_kwargs: dict = {}
        chunks = [_delta_chunk("Hi", role="assistant")]
        service, tracer = _make_service(_stream_gateway(chunks, captured_kwargs))

        await service.chat_completion_stream_auto_send(
            task_id="task-1",
            llm_config=LLMConfig(model="gpt-4o", messages=[], stream=True),
            trace_id="trace-1",
        )

        assert "usage" not in tracer.trace_obj.spans[0].output
