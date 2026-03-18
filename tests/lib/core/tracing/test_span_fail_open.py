from __future__ import annotations

from typing import Any
from unittest.mock import Mock, AsyncMock

import pytest

from agentex.lib.core.tracing.trace import Trace, AsyncTrace


class FakeSyncProcessor:
    def __init__(self, *, fail_on_start: bool = False, fail_on_end: bool = False):
        self.fail_on_start = fail_on_start
        self.fail_on_end = fail_on_end
        self.started: list[Any] = []
        self.ended: list[Any] = []

    def on_span_start(self, span: Any) -> None:
        self.started.append(span)
        if self.fail_on_start:
            raise ConnectionError("tracing backend unavailable")

    def on_span_end(self, span: Any) -> None:
        self.ended.append(span)
        if self.fail_on_end:
            raise ConnectionError("tracing backend unavailable")


class FakeAsyncProcessor:
    def __init__(self, *, fail_on_start: bool = False, fail_on_end: bool = False):
        self.fail_on_start = fail_on_start
        self.fail_on_end = fail_on_end
        self.started: list[Any] = []
        self.ended: list[Any] = []

    async def on_span_start(self, span: Any) -> None:
        self.started.append(span)
        if self.fail_on_start:
            raise ConnectionError("tracing backend unavailable")

    async def on_span_end(self, span: Any) -> None:
        self.ended.append(span)
        if self.fail_on_end:
            raise ConnectionError("tracing backend unavailable")


# ---------------------------------------------------------------------------
# Sync Trace tests
# ---------------------------------------------------------------------------


class TestSyncSpanFailOpen:
    def _make_trace(self, processor: FakeSyncProcessor) -> Trace:
        return Trace(
            processors=[processor],  # type: ignore[list-item]
            client=Mock(),
            trace_id="test-trace",
        )

    def test_default_propagates_start_error(self) -> None:
        proc = FakeSyncProcessor(fail_on_start=True)
        trace = self._make_trace(proc)
        with pytest.raises(ConnectionError):
            with trace.span(name="test"):
                pass

    def test_default_propagates_end_error(self) -> None:
        proc = FakeSyncProcessor(fail_on_end=True)
        trace = self._make_trace(proc)
        with pytest.raises(ConnectionError):
            with trace.span(name="test"):
                pass

    def test_fail_open_suppresses_start_error(self) -> None:
        proc = FakeSyncProcessor(fail_on_start=True)
        trace = self._make_trace(proc)
        with trace.span(name="test", fail_open=True) as span:
            assert span is None

    def test_fail_open_suppresses_end_error(self) -> None:
        proc = FakeSyncProcessor(fail_on_end=True)
        trace = self._make_trace(proc)
        with trace.span(name="test", fail_open=True) as span:
            assert span is not None

    def test_fail_open_does_not_swallow_body_exception(self) -> None:
        """The critical property: exceptions from the caller's code must propagate."""
        proc = FakeSyncProcessor()
        trace = self._make_trace(proc)
        with pytest.raises(ValueError, match="business logic error"):
            with trace.span(name="test", fail_open=True):
                raise ValueError("business logic error")

    def test_fail_open_body_exception_with_end_error(self) -> None:
        """Body exception propagates even when end_span also fails."""
        proc = FakeSyncProcessor(fail_on_end=True)
        trace = self._make_trace(proc)
        with pytest.raises(ValueError, match="business logic error"):
            with trace.span(name="test", fail_open=True):
                raise ValueError("business logic error")

    def test_happy_path_unchanged(self) -> None:
        proc = FakeSyncProcessor()
        trace = self._make_trace(proc)
        with trace.span(name="test") as span:
            assert span is not None
            assert span.name == "test"
        assert len(proc.started) == 1
        assert len(proc.ended) == 1

    def test_no_trace_id_yields_none(self) -> None:
        trace = Trace(processors=[], client=Mock(), trace_id=None)
        with trace.span(name="test", fail_open=True) as span:
            assert span is None


# ---------------------------------------------------------------------------
# Async Trace tests
# ---------------------------------------------------------------------------


class TestAsyncSpanFailOpen:
    def _make_trace(self, processor: FakeAsyncProcessor) -> AsyncTrace:
        return AsyncTrace(
            processors=[processor],  # type: ignore[list-item]
            client=AsyncMock(),
            trace_id="test-trace",
        )

    @pytest.mark.asyncio
    async def test_default_propagates_start_error(self) -> None:
        proc = FakeAsyncProcessor(fail_on_start=True)
        trace = self._make_trace(proc)
        with pytest.raises(ConnectionError):
            async with trace.span(name="test"):
                pass

    @pytest.mark.asyncio
    async def test_default_propagates_end_error(self) -> None:
        proc = FakeAsyncProcessor(fail_on_end=True)
        trace = self._make_trace(proc)
        with pytest.raises(ConnectionError):
            async with trace.span(name="test"):
                pass

    @pytest.mark.asyncio
    async def test_fail_open_suppresses_start_error(self) -> None:
        proc = FakeAsyncProcessor(fail_on_start=True)
        trace = self._make_trace(proc)
        async with trace.span(name="test", fail_open=True) as span:
            assert span is None

    @pytest.mark.asyncio
    async def test_fail_open_suppresses_end_error(self) -> None:
        proc = FakeAsyncProcessor(fail_on_end=True)
        trace = self._make_trace(proc)
        async with trace.span(name="test", fail_open=True) as span:
            assert span is not None

    @pytest.mark.asyncio
    async def test_fail_open_does_not_swallow_body_exception(self) -> None:
        """The critical property: exceptions from the caller's code must propagate."""
        proc = FakeAsyncProcessor()
        trace = self._make_trace(proc)
        with pytest.raises(ValueError, match="business logic error"):
            async with trace.span(name="test", fail_open=True):
                raise ValueError("business logic error")

    @pytest.mark.asyncio
    async def test_fail_open_body_exception_with_end_error(self) -> None:
        """Body exception propagates even when end_span also fails."""
        proc = FakeAsyncProcessor(fail_on_end=True)
        trace = self._make_trace(proc)
        with pytest.raises(ValueError, match="business logic error"):
            async with trace.span(name="test", fail_open=True):
                raise ValueError("business logic error")

    @pytest.mark.asyncio
    async def test_happy_path_unchanged(self) -> None:
        proc = FakeAsyncProcessor()
        trace = self._make_trace(proc)
        async with trace.span(name="test") as span:
            assert span is not None
            assert span.name == "test"
        assert len(proc.started) == 1
        assert len(proc.ended) == 1

    @pytest.mark.asyncio
    async def test_no_trace_id_yields_none(self) -> None:
        trace = AsyncTrace(processors=[], client=AsyncMock(), trace_id=None)
        async with trace.span(name="test", fail_open=True) as span:
            assert span is None
