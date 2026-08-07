"""Tests for the obs-wrapper -> ambient-correlation fallback.

Regression coverage for: in ``lgtm`` mode with no OTel TracerProvider installed
(the documented current state of agents), ``open_obs_span`` used to return a
handle carrying an *empty* correlation. At the call site (``trace.py``) that
handle is not None, so the ambient ``obs_correlation()`` fallback was never
consulted and the business span ended up with **no** ``obs_*`` ids at all --
strictly worse than falling back.

The fix: ``open_obs_span`` bails out to ``None`` when the wrapper span's context
is invalid (proxy ``NonRecordingSpan``), so the caller falls back to the ambient
obs ids. These tests pin:

  - invalid wrapper context -> ``open_obs_span`` returns ``None`` and restores
    the active context (no leaked attach),
  - valid wrapper context -> a handle with real 32/16-hex correlation,
  - end-to-end: with an invalid wrapper but a valid *ambient* span active,
    ``Trace.start_span`` stamps the ambient ``obs_trace_id`` / ``obs_span_id``
    onto the business span (the fallback fires).
"""

from __future__ import annotations

from typing import Any, cast

import pytest
from opentelemetry import trace as otel_trace, context as otel_context
from opentelemetry.trace import (
    INVALID_SPAN_CONTEXT,
    TraceFlags,
    SpanContext,
    NonRecordingSpan,
    set_span_in_context,
)

from agentex.lib.core.tracing.trace import Trace
from agentex.lib.core.tracing.obs_span import open_obs_span, close_obs_span

# Deterministic, valid ids for the "provider present" / ambient-span cases.
_TRACE_ID = 0x0123456789ABCDEF0123456789ABCDEF
_SPAN_ID = 0x0123456789ABCDEF
_TRACE_HEX = format(_TRACE_ID, "032x")
_SPAN_HEX = format(_SPAN_ID, "016x")


def _valid_span() -> NonRecordingSpan:
    ctx = SpanContext(
        trace_id=_TRACE_ID,
        span_id=_SPAN_ID,
        is_remote=False,
        trace_flags=TraceFlags(TraceFlags.SAMPLED),
    )
    return NonRecordingSpan(ctx)


class _FakeTracer:
    """A tracer whose start_span returns a fixed span (bypasses any real provider)."""

    def __init__(self, span: NonRecordingSpan):
        self._span = span

    def start_span(self, name: str, *args: object, **kwargs: object) -> NonRecordingSpan:
        return self._span


def _patch_wrapper_tracer(monkeypatch: pytest.MonkeyPatch, span: NonRecordingSpan) -> None:
    """Force the obs wrapper's ``trace.get_tracer(...).start_span`` to yield ``span``.

    Only affects the wrapper opened inside open_obs_span; obs_correlation reads
    the *current* span via ``trace.get_current_span()`` and is untouched.
    """
    monkeypatch.setattr(otel_trace, "get_tracer", lambda *a, **k: _FakeTracer(span))


def test_open_obs_span_returns_none_on_invalid_context(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SGP_OBS_MODE", "lgtm")
    _patch_wrapper_tracer(monkeypatch, NonRecordingSpan(INVALID_SPAN_CONTEXT))

    before = otel_trace.get_current_span()
    handle = open_obs_span("step", business_span_id="bs", business_trace_id="bt")

    # No handle -> caller falls back to obs_correlation() instead of an empty {}.
    assert handle is None
    # The context attach inside open_obs_span was detached: no leak.
    assert otel_trace.get_current_span() is before


def test_open_obs_span_returns_handle_on_valid_context(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SGP_OBS_MODE", "lgtm")
    _patch_wrapper_tracer(monkeypatch, _valid_span())

    handle = open_obs_span("step", business_span_id="bs", business_trace_id="bt")

    assert handle is not None
    assert handle.correlation == {"obs_trace_id": _TRACE_HEX, "obs_span_id": _SPAN_HEX}
    close_obs_span(handle)


def test_start_span_falls_back_to_ambient_when_wrapper_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    """End-to-end: invalid wrapper -> ambient obs ids land on the business span."""
    monkeypatch.setenv("SGP_OBS_MODE", "lgtm")
    # Wrapper span has an invalid context (no real provider) -> open_obs_span None.
    _patch_wrapper_tracer(monkeypatch, NonRecordingSpan(INVALID_SPAN_CONTEXT))

    # But a VALID ambient span is active (e.g. the ACP ingress / interceptor span).
    token = otel_context.attach(set_span_in_context(_valid_span()))
    try:
        trace_obj = Trace(processors=[], client=cast(Any, object()), trace_id="trace-1")
        span = trace_obj.start_span(name="step")
    finally:
        otel_context.detach(token)

    # obs_correlation() was consulted and stamped the ambient ids onto data.
    assert isinstance(span.data, dict)
    assert span.data["obs_trace_id"] == _TRACE_HEX
    assert span.data["obs_span_id"] == _SPAN_HEX
