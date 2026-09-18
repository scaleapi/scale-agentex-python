from __future__ import annotations

import dataclasses
from typing import Any, override
from unittest.mock import Mock, AsyncMock

import pytest
from temporalio import activity
from opentelemetry import trace
from temporalio.worker import Worker, Interceptor, ExecuteActivityInput, ActivityInboundInterceptor
from temporalio.testing import ActivityEnvironment
from opentelemetry.sdk.trace import TracerProvider
from temporalio.bridge.client import Client as BridgeClient
from temporalio.bridge.worker import Worker as BridgeWorker
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from temporalio.contrib.opentelemetry import TracingInterceptor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from agentex.lib.core.temporal.workers.worker import AgentexWorker


class _BusinessInterceptor(Interceptor):
    def __init__(self, name: str, events: list[tuple[str, bool]]) -> None:
        self.name = name
        self.events = events

    @override
    def intercept_activity(self, next: ActivityInboundInterceptor) -> ActivityInboundInterceptor:
        owner = self

        class Inbound(ActivityInboundInterceptor):
            @override
            async def execute_activity(self, input: ExecuteActivityInput) -> Any:
                owner.events.append((owner.name, trace.get_current_span().get_span_context().is_valid))
                return await self.next.execute_activity(input)

        return Inbound(next)


class _ActivityCall(ActivityInboundInterceptor):
    def __init__(self) -> None:
        pass

    @override
    async def execute_activity(self, input: ExecuteActivityInput) -> Any:
        return await input.fn(*input.args)


@pytest.mark.parametrize("tracing_enabled", [True, False])
async def test_worker_inherits_one_tracing_interceptor_before_business_interceptors(
    monkeypatch: pytest.MonkeyPatch, tracing_enabled: bool
) -> None:
    monkeypatch.setenv("AGENTEX_TEMPORAL_TRACE_INTERCEPTOR_ENABLED", str(tracing_enabled).lower())
    monkeypatch.delenv("DD_AGENT_HOST", raising=False)
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer(__name__)
    monkeypatch.setattr(trace, "get_tracer", lambda *args, **kwargs: tracer)
    # Keep Client and Worker configuration real; replace their network boundary.
    monkeypatch.setattr(BridgeClient, "connect", AsyncMock(return_value=Mock()))
    monkeypatch.setattr(BridgeWorker, "create", Mock(return_value=Mock()))

    events: list[tuple[str, bool]] = []
    first = _BusinessInterceptor("first", events)
    second = _BusinessInterceptor("second", events)

    @activity.defn
    async def sample_activity() -> str:
        events.append(("activity", trace.get_current_span().get_span_context().is_valid))
        return "completed"

    async def run_once(worker: Worker) -> None:
        assert worker._activity_worker is not None
        interceptors = worker._activity_worker._interceptors
        assert sum(isinstance(item, TracingInterceptor) for item in interceptors) == int(tracing_enabled)
        assert list(interceptors[-2:]) == [first, second]

        inbound: ActivityInboundInterceptor = _ActivityCall()
        for interceptor in reversed(interceptors):
            inbound = interceptor.intercept_activity(inbound)
        environment = ActivityEnvironment()
        environment.info = dataclasses.replace(environment.info, activity_type="sample_activity")
        result = await environment.run(
            inbound.execute_activity,
            ExecuteActivityInput(fn=sample_activity, args=[], executor=None, headers={}),
        )
        assert result == "completed"

    monkeypatch.setattr(Worker, "run", run_once)
    worker = AgentexWorker(task_queue="test-tracing", health_check_port=8080, interceptors=[first, second])
    monkeypatch.setattr(worker, "start_health_check_server", AsyncMock())
    monkeypatch.setattr(worker, "_register_agent", AsyncMock())

    try:
        await worker.run(activities=[sample_activity], workflows=[])
        assert events == [("first", tracing_enabled), ("second", tracing_enabled), ("activity", tracing_enabled)]
        spans = exporter.get_finished_spans()
        assert len(spans) == int(tracing_enabled)
        if tracing_enabled:
            assert spans[0].name == "RunActivity:sample_activity"
    finally:
        provider.shutdown()
