"""Tests that the openai_agents streaming model copies real token usage onto spans.

The backend bills per-call usage from ``span.output["usage"]``; these tests
assert the streaming model writes the API-reported usage there (and into the
returned ``ModelResponse.usage``) instead of dropping it.
"""

from __future__ import annotations

from typing import Any
from datetime import UTC, datetime
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from agents import ModelSettings
from openai.types.responses import Response, ResponseCompletedEvent
from openai.types.responses.response_usage import (
    ResponseUsage,
    InputTokensDetails,
    OutputTokensDetails,
)

import agentex.lib.core.temporal.plugins.openai_agents.models.temporal_streaming_model as tsm
from agentex.types.span import Span
from agentex.lib.core.temporal.plugins.openai_agents.interceptors.context_interceptor import (
    streaming_task_id,
    streaming_trace_id,
    streaming_parent_span_id,
)

pytestmark = pytest.mark.asyncio


class FakeTrace:
    """Captures spans handed out by trace.span() so tests can inspect them."""

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
            data=data,
            task_id=task_id,
        )
        self.spans.append(span)
        yield span


class FakeTracer:
    def __init__(self) -> None:
        self.trace_obj = FakeTrace()

    def trace(self, trace_id):
        return self.trace_obj


@pytest.fixture
def tracing_contextvars():
    tokens = [
        streaming_task_id.set("task-1"),
        streaming_trace_id.set("trace-1"),
        streaming_parent_span_id.set("parent-span-1"),
    ]
    yield
    streaming_task_id.reset(tokens[0])
    streaming_trace_id.reset(tokens[1])
    streaming_parent_span_id.reset(tokens[2])


EXPECTED_USAGE_BLOB = {
    "input_tokens": 120,
    "output_tokens": 80,
    "total_tokens": 200,
    "cached_input_tokens": 30,
    "reasoning_tokens": 40,
}


def _output_dict(span: Span) -> dict[str, Any]:
    assert isinstance(span.output, dict)
    return span.output


class FakeStream:
    def __init__(self, events) -> None:
        self._events = events

    def __aiter__(self):
        async def gen():
            for event in self._events:
                yield event

        return gen()


class TestTemporalStreamingModel:
    async def test_streaming_model_captures_final_response_usage(self, tracing_contextvars):
        usage = ResponseUsage(
            input_tokens=120,
            output_tokens=80,
            total_tokens=200,
            input_tokens_details=InputTokensDetails(cached_tokens=30),
            output_tokens_details=OutputTokensDetails(reasoning_tokens=40),
        )
        completed = ResponseCompletedEvent.model_construct(
            type="response.completed",
            response=Response.model_construct(output=[], usage=usage),
        )

        fake_tracer = FakeTracer()
        openai_client = MagicMock()
        openai_client.responses.create = AsyncMock(return_value=FakeStream([completed]))

        with patch.object(tsm, "create_async_agentex_client", return_value=MagicMock()):
            with patch.object(tsm, "AsyncTracer", return_value=fake_tracer):
                model = tsm.TemporalStreamingModel(model_name="gpt-4o", openai_client=openai_client)

        response = await model.get_response(
            system_instructions=None,
            input="hello",
            model_settings=ModelSettings(),
            tools=[],
            output_schema=None,
            handoffs=[],
            tracing=None,
        )

        # Real usage lands on the returned ModelResponse (was zeroed before)
        assert response.usage.input_tokens == 120
        assert response.usage.output_tokens == 80
        assert response.usage.total_tokens == 200
        assert response.usage.input_tokens_details.cached_tokens == 30
        assert response.usage.output_tokens_details.reasoning_tokens == 40

        # And on the span output for billing
        assert len(fake_tracer.trace_obj.spans) == 1
        span = fake_tracer.trace_obj.spans[0]
        assert _output_dict(span)["usage"] == EXPECTED_USAGE_BLOB

    async def test_streaming_model_writes_zero_usage_when_api_reports_none(self, tracing_contextvars):
        completed = ResponseCompletedEvent.model_construct(
            type="response.completed",
            response=Response.model_construct(output=[], usage=None),
        )

        fake_tracer = FakeTracer()
        openai_client = MagicMock()
        openai_client.responses.create = AsyncMock(return_value=FakeStream([completed]))

        with patch.object(tsm, "create_async_agentex_client", return_value=MagicMock()):
            with patch.object(tsm, "AsyncTracer", return_value=fake_tracer):
                model = tsm.TemporalStreamingModel(model_name="gpt-4o", openai_client=openai_client)

        response = await model.get_response(
            system_instructions=None,
            input="hello",
            model_settings=ModelSettings(),
            tools=[],
            output_schema=None,
            handoffs=[],
            tracing=None,
        )

        # No usage from the API: the model reports zeros rather than omitting,
        # so billing sums 0 instead of missing the span
        assert response.usage.input_tokens == 0
        span = fake_tracer.trace_obj.spans[0]
        assert _output_dict(span)["usage"] == {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "cached_input_tokens": 0,
            "reasoning_tokens": 0,
        }
