from __future__ import annotations

import uuid
from typing import Any
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from agentex.types.span import Span
from agentex.lib.core.tracing.trace import Trace, AsyncTrace
from agentex.lib.core.tracing.span_error import (
    SPAN_ERROR_KEY,
    get_span_error,
    set_span_error,
)

PROCESSOR_MODULE = "agentex.lib.core.tracing.processors.sgp_tracing_processor"


def _make_span(data=None) -> Span:
    return Span(
        id=str(uuid.uuid4()),
        name="test-span",
        start_time=datetime.now(UTC),
        trace_id="trace-1",
        data=data,
    )


# ---------------------------------------------------------------------------
# Helpers: set_span_error / get_span_error
# ---------------------------------------------------------------------------


class TestSpanErrorHelpers:
    def test_set_then_get_on_none_data(self):
        span = _make_span(data=None)
        set_span_error(span, ValueError("boom"))
        assert get_span_error(span) == {"type": "ValueError", "message": "boom"}
        assert isinstance(span.data, dict)
        assert span.data[SPAN_ERROR_KEY] == {"type": "ValueError", "message": "boom"}

    def test_set_preserves_existing_dict_keys(self):
        span = _make_span(data={"__span_type__": "LLM"})
        set_span_error(span, RuntimeError("nope"))
        assert isinstance(span.data, dict)
        assert span.data["__span_type__"] == "LLM"
        err = get_span_error(span)
        assert err is not None
        assert err["type"] == "RuntimeError"

    def test_get_returns_none_when_no_error(self):
        assert get_span_error(_make_span(data={"foo": "bar"})) is None
        assert get_span_error(_make_span(data=None)) is None

    def test_set_is_noop_on_list_data(self):
        span = _make_span(data=[{"a": 1}])
        set_span_error(span, ValueError("boom"))
        # list-shaped data is left untouched (mirrors _add_source_to_span)
        assert span.data == [{"a": 1}]
        assert get_span_error(span) is None


# ---------------------------------------------------------------------------
# Capture: the context managers record body exceptions onto the span
# ---------------------------------------------------------------------------


class TestContextManagerCapture:
    def test_sync_span_records_error_and_reraises(self):
        trace = Trace(processors=[], client=MagicMock(), trace_id="t1")
        captured = {}
        with pytest.raises(ValueError, match="boom"):
            with trace.span("op") as span:
                captured["span"] = span
                raise ValueError("boom")
        err = get_span_error(captured["span"])
        assert err == {"type": "ValueError", "message": "boom"}

    def test_sync_span_success_has_no_error(self):
        trace = Trace(processors=[], client=MagicMock(), trace_id="t1")
        with trace.span("op") as span:
            pass
        assert get_span_error(span) is None

    @pytest.mark.asyncio
    async def test_async_span_records_error_and_reraises(self):
        trace = AsyncTrace(processors=[], client=MagicMock(), trace_id="t1")
        captured = {}
        with pytest.raises(RuntimeError, match="kaboom"):
            async with trace.span("op") as span:
                captured["span"] = span
                raise RuntimeError("kaboom")
        err = get_span_error(captured["span"])
        assert err == {"type": "RuntimeError", "message": "kaboom"}


# ---------------------------------------------------------------------------
# Map: _build_sgp_span translates the recorded error into SGP status=ERROR
# ---------------------------------------------------------------------------


class _FakeSGPSpan:
    def __init__(self, metadata: dict[str, Any] | None) -> None:
        self.status = "SUCCESS"
        self.metadata: dict[str, Any] = metadata if metadata is not None else {}
        self.start_time = None

    def set_error(
        self,
        error_type: str | None = None,
        error_message: str | None = None,
        exception: BaseException | None = None,
    ) -> None:
        self.status = "ERROR"
        self.metadata["error"] = True
        self.metadata["error_type"] = error_type
        self.metadata["error_message"] = error_message


def _fake_create_span(**kwargs: Any) -> _FakeSGPSpan:
    return _FakeSGPSpan(kwargs.get("metadata"))


class TestBuildSGPSpanMapping:
    @staticmethod
    def _env():
        return MagicMock(ACP_TYPE=None, AGENT_NAME=None, AGENT_ID=None)

    def test_error_maps_to_status_error(self):
        from agentex.lib.core.tracing.processors.sgp_tracing_processor import _build_sgp_span

        span = _make_span(data={SPAN_ERROR_KEY: {"type": "ValueError", "message": "boom"}})
        with patch(f"{PROCESSOR_MODULE}.create_span", side_effect=_fake_create_span):
            sgp_span = _build_sgp_span(span, self._env())

        assert sgp_span.status == "ERROR"
        assert sgp_span.metadata["error"] is True
        assert sgp_span.metadata["error_type"] == "ValueError"
        assert sgp_span.metadata["error_message"] == "boom"

    def test_no_error_leaves_status_success(self):
        from agentex.lib.core.tracing.processors.sgp_tracing_processor import _build_sgp_span

        span = _make_span(data={"__span_type__": "LLM"})
        with patch(f"{PROCESSOR_MODULE}.create_span", side_effect=_fake_create_span):
            sgp_span = _build_sgp_span(span, self._env())

        assert sgp_span.status == "SUCCESS"
        assert "error" not in sgp_span.metadata
