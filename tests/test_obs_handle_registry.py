"""Tests for the obs-handle registry: leak safety + app-path safety.

Two guarantees are pinned here:

  1. A tracing processor whose ``on_span_start`` / ``on_span_end`` raises must
     NOT crash the app path (``start_span`` / ``end_span`` still return). Because
     start_span returns normally, the standard end_span path still pops+closes
     the obs handle -- so the registration-order leak Greptile flagged cannot
     happen.
  2. ``_OBS_HANDLES`` is bounded: a caller that starts spans without ending them
     (public, unpaired ``start_span`` / ``end_span`` API) degrades gracefully --
     the oldest handle is evicted AND closed rather than growing unbounded.
"""

from __future__ import annotations

from typing import Any, cast

import pytest
from opentelemetry import trace as otel_trace
from opentelemetry.trace import (
    TraceFlags,
    SpanContext,
    NonRecordingSpan,
)

import agentex.lib.core.tracing.trace as trace_mod
from agentex.types.span import Span
from agentex.lib.core.tracing.trace import _OBS_HANDLES, _OBS_HANDLES_MAX, Trace


class _FakeHandle:
    """Minimal stand-in for a sgp_obs ``ObsSpanHandle`` — the registry only ever
    calls ``close()`` on eviction, so that's all we implement."""

    def __init__(self, on_close: Any = None) -> None:
        self.correlation: dict[str, str] = {}
        self._on_close = on_close

    def close(self, error: Any = None) -> None:
        if self._on_close is not None:
            self._on_close(error)


@pytest.fixture(autouse=True)
def _clear_registry() -> Any:
    """The registry is module-level global; keep tests isolated."""
    _OBS_HANDLES.clear()
    yield
    _OBS_HANDLES.clear()


def _valid_wrapper_span() -> NonRecordingSpan:
    ctx = SpanContext(
        trace_id=0x0123456789ABCDEF0123456789ABCDEF,
        span_id=0x0123456789ABCDEF,
        is_remote=False,
        trace_flags=TraceFlags(TraceFlags.SAMPLED),
    )
    return NonRecordingSpan(ctx)


class _RaisingProcessor:
    """A processor whose lifecycle hooks blow up -- an obs bug must not crash the app."""

    def __init__(self) -> None:
        self.started = 0
        self.ended = 0

    def on_span_start(self, span: Span) -> None:
        self.started += 1
        raise RuntimeError("processor on_span_start is broken")

    def on_span_end(self, span: Span) -> None:
        self.ended += 1
        raise RuntimeError("processor on_span_end is broken")


def _trace_with(processors: list[Any]) -> Trace:
    return Trace(processors=processors, client=cast(Any, object()), trace_id="trace-1")


def test_start_span_survives_raising_processor_and_no_leak(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SGP_OBS_MODE", "lgtm")
    # Wrapper opens with a valid context -> a real handle is registered.
    monkeypatch.setattr(
        otel_trace,
        "get_tracer",
        lambda *a, **k: type("T", (), {"start_span": staticmethod(lambda *a, **k: _valid_wrapper_span())})(),
    )

    proc = _RaisingProcessor()
    trace_obj = _trace_with([proc])

    # A processor exploding in on_span_start must NOT propagate.
    span = trace_obj.start_span(name="step")
    assert proc.started == 1
    # The handle was registered despite the processor blowing up afterwards.
    assert span.id in _OBS_HANDLES

    # end_span also survives a raising on_span_end AND pops/closes the handle,
    # so nothing leaks.
    trace_obj.end_span(span)
    assert proc.ended == 1
    assert span.id not in _OBS_HANDLES


def test_registry_is_bounded_and_evicts_and_closes_oldest() -> None:
    closed: list[str] = []

    def _make_handle(marker: str) -> _FakeHandle:
        return _FakeHandle(on_close=lambda _err=None, _m=marker: closed.append(_m))

    # Fill exactly to the cap: nothing evicted yet.
    for i in range(_OBS_HANDLES_MAX):
        trace_mod._register_obs_handle(f"span-{i}", _make_handle(f"span-{i}"))
    assert len(_OBS_HANDLES) == _OBS_HANDLES_MAX
    assert closed == []

    # One over the cap: the OLDEST (span-0) is evicted AND closed.
    trace_mod._register_obs_handle("span-overflow", _make_handle("span-overflow"))
    assert len(_OBS_HANDLES) == _OBS_HANDLES_MAX
    assert "span-0" not in _OBS_HANDLES
    assert "span-overflow" in _OBS_HANDLES
    assert closed == ["span-0"]  # evicted handle was closed, not just dropped


def test_reinserting_same_span_id_refreshes_recency() -> None:
    def _noop_handle() -> _FakeHandle:
        return _FakeHandle()

    trace_mod._register_obs_handle("a", _noop_handle())
    trace_mod._register_obs_handle("b", _noop_handle())
    # Touch "a" again -> it becomes the most-recent, so "b" is now the oldest.
    trace_mod._register_obs_handle("a", _noop_handle())

    oldest_key = next(iter(_OBS_HANDLES))
    assert oldest_key == "b"
