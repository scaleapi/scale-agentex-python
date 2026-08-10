"""Tests for the Temporal-path obs backend selection.

Inside a Temporal activity the ambient span is temporalio's OpenTelemetry
``TracingInterceptor`` span -- always OTel, regardless of ``SGP_OBS_MODE``. The
reverse tag (``tag_ambient_obs_span``) and the forward correlation read
(``obs_correlation``) must therefore target OTel there, even in the default
``dd_only`` mode. Before the fix they branched on ``SGP_OBS_MODE`` and, in
``dd_only``, tagged/read an unrelated ddtrace span -- so the business<->obs
correlation on the async/Temporal path pointed at the wrong trace (or nowhere).
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import pytest
from opentelemetry import trace as otel_trace
from opentelemetry.trace import TraceFlags, SpanContext
from temporalio import activity as temporal_activity

import agentex.lib.core.tracing.trace as trace_mod
import agentex.lib.core.tracing.obs_ids as obs_ids_mod
from agentex.lib.core.tracing.trace import _OBS_HANDLES, Trace
from agentex.lib.core.tracing.obs_ids import obs_correlation
from agentex.lib.core.tracing.obs_span import tag_ambient_obs_span
from agentex.lib.core.temporal.activities.adk.tracing_activities import TracingActivityName

_TRACE_ID = 0x0123456789ABCDEF0123456789ABCDEF
_SPAN_ID = 0x0123456789ABCDEF
_TRACE_HEX = format(_TRACE_ID, "032x")
_SPAN_HEX = format(_SPAN_ID, "016x")


def _valid_ctx() -> SpanContext:
    return SpanContext(
        trace_id=_TRACE_ID,
        span_id=_SPAN_ID,
        is_remote=True,  # like a Temporal-propagated remote parent
        trace_flags=TraceFlags(TraceFlags.SAMPLED),
    )


class _RecordingOtelSpan:
    """A stand-in for the interceptor's activity span that records set_attribute."""

    def __init__(self, ctx: SpanContext) -> None:
        self._ctx = ctx
        self.attributes: dict[str, Any] = {}

    def get_span_context(self) -> SpanContext:
        return self._ctx

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value


@pytest.fixture(autouse=True)
def _clear_registry() -> Any:
    _OBS_HANDLES.clear()
    yield
    _OBS_HANDLES.clear()


def _activate_otel_span(monkeypatch: pytest.MonkeyPatch) -> _RecordingOtelSpan:
    span = _RecordingOtelSpan(_valid_ctx())
    monkeypatch.setattr(otel_trace, "get_current_span", lambda *a, **k: span)
    return span


def test_temporal_path_tags_and_reads_otel_in_dd_only(monkeypatch: pytest.MonkeyPatch) -> None:
    # Default/dd_only mode is exactly where the old code went to ddtrace.
    # Tagging the ambient interceptor span (no wrapper) now applies only inside
    # the SDK's dispatched START_SPAN/END_SPAN activity, not any activity.
    monkeypatch.setenv("SGP_OBS_MODE", "dd_only")
    monkeypatch.setattr(trace_mod, "_in_tracing_dispatch_activity", lambda: True)
    activity_span = _activate_otel_span(monkeypatch)

    trace_obj = Trace(processors=[], client=cast(Any, object()), trace_id="trace-1")
    span = trace_obj.start_span(name="process_turn")

    # Reverse tag landed on the OTel activity span (not a ddtrace span / nowhere).
    assert activity_span.attributes["agentex.business_span_id"] == span.id
    assert activity_span.attributes["agentex.business_trace_id"] == "trace-1"

    # Forward correlation recorded the OTel activity trace ids.
    assert isinstance(span.data, dict)
    assert span.data["obs_trace_id"] == _TRACE_HEX
    assert span.data["obs_span_id"] == _SPAN_HEX

    # Temporal path opens no wrapper -> no handle registered (nothing to leak).
    assert span.id not in _OBS_HANDLES


def test_obs_correlation_prefer_otel_prefers_otel_over_ddtrace(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SGP_OBS_MODE", "dd_only")
    _activate_otel_span(monkeypatch)
    # Make ddtrace resolve to DIFFERENT ids so we can prove which backend won.
    monkeypatch.setattr(obs_ids_mod, "_ddtrace_ids", lambda: ("d" * 32, "e" * 16))

    # prefer_otel (Temporal path): OTel wins even though mode is dd_only.
    assert obs_correlation(prefer_otel=True) == {"obs_trace_id": _TRACE_HEX, "obs_span_id": _SPAN_HEX}
    # Default (in-process path): still honors mode -> ddtrace.
    assert obs_correlation() == {"obs_trace_id": "d" * 32, "obs_span_id": "e" * 16}


def test_tag_ambient_prefer_otel_falls_back_to_ddtrace(monkeypatch: pytest.MonkeyPatch) -> None:
    """When no valid OTel span is active, prefer_otel falls back to ddtrace."""
    monkeypatch.setenv("SGP_OBS_MODE", "dd_only")

    # No valid OTel span active.
    invalid = _RecordingOtelSpan(otel_trace.INVALID_SPAN_CONTEXT)
    monkeypatch.setattr(otel_trace, "get_current_span", lambda *a, **k: invalid)

    tagged: dict[str, Any] = {}

    class _FakeDDSpan:
        def set_tag(self, k: str, v: Any) -> None:
            tagged[k] = v

    class _FakeDDTracer:
        def current_span(self) -> _FakeDDSpan:
            return _FakeDDSpan()

    # obs_span imports `from ddtrace.trace import tracer` lazily; inject a stub module.
    import sys
    import types

    ddtrace_trace = types.ModuleType("ddtrace.trace")
    ddtrace_trace.tracer = _FakeDDTracer()  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "ddtrace.trace", ddtrace_trace)

    tag_ambient_obs_span(business_span_id="bs", business_trace_id="bt", prefer_otel=True)

    # OTel was invalid -> fell back to ddtrace, which got the reverse tag.
    assert tagged["agentex.business_span_id"] == "bs"
    assert tagged["agentex.business_trace_id"] == "bt"
    # The invalid OTel span was NOT tagged.
    assert invalid.attributes == {}


class _FakeHandle:
    def __init__(self, corr):
        self.correlation = corr


def test_begin_obs_opens_wrapper_outside_dispatch_activity(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sync path or inside a business Temporal activity: open a per-step wrapper
    (1:1), not the ambient-span tag. Each business span gets its own obs span."""
    monkeypatch.setattr(trace_mod, "_in_tracing_dispatch_activity", lambda: False)
    monkeypatch.setattr(
        trace_mod, "open_obs_span",
        lambda *a, **k: _FakeHandle({"obs_trace_id": "t1", "obs_span_id": "s1"}),
    )
    handle, corr = trace_mod._begin_obs("mortgage.classify_intent", "bs", "bt")
    assert handle is not None
    assert corr == {"obs_trace_id": "t1", "obs_span_id": "s1"}


def test_begin_obs_tags_ambient_inside_dispatch_activity(monkeypatch: pytest.MonkeyPatch) -> None:
    """Inside the dispatched START_SPAN/END_SPAN activity: no wrapper (would leak
    across activities); tag the ambient interceptor span instead."""
    monkeypatch.setattr(trace_mod, "_in_tracing_dispatch_activity", lambda: True)
    tagged: dict = {}
    monkeypatch.setattr(trace_mod, "tag_ambient_obs_span", lambda **k: tagged.update(k))
    monkeypatch.setattr(trace_mod, "obs_correlation", lambda **k: {"obs_trace_id": "amb", "obs_span_id": "amb"})
    handle, corr = trace_mod._begin_obs("mortgage.advisor.turn", "bs", "bt")
    assert handle is None
    assert tagged.get("business_span_id") == "bs" and tagged.get("prefer_otel") is True
    assert corr == {"obs_trace_id": "amb", "obs_span_id": "amb"}


def test_business_activity_dd_only_reads_otel_not_ddtrace(monkeypatch: pytest.MonkeyPatch) -> None:
    """Regression: inside a BUSINESS activity (not the dispatched start/end-span)
    with default dd_only mode, the per-step wrapper branch must prefer OTel. The
    ambient span is the temporalio OTel interceptor span regardless of mode; a
    dd_only ddtrace read finds no request context in a worker, so before the fix
    the business span persisted with empty obs ids. Assert it carries the OTel
    activity ids, not ddtrace's."""
    monkeypatch.setenv("SGP_OBS_MODE", "dd_only")
    monkeypatch.setattr(trace_mod, "_in_tracing_dispatch_activity", lambda: False)
    monkeypatch.setattr(trace_mod, "_in_temporal_activity", lambda: True)
    # Make ddtrace resolve to DIFFERENT ids so we can prove which backend won.
    monkeypatch.setattr(obs_ids_mod, "_ddtrace_ids", lambda: ("d" * 32, "e" * 16))
    _activate_otel_span(monkeypatch)  # valid OTel span active (the interceptor span)

    trace_obj = Trace(processors=[], client=cast(Any, object()), trace_id="trace-1")
    span = trace_obj.start_span(name="mortgage.classify_intent")

    assert isinstance(span.data, dict)
    # OTel ids, not ddtrace's ("d"*32) and not empty.
    assert span.data["obs_trace_id"] == _TRACE_HEX
    assert span.data["obs_span_id"] == _SPAN_HEX


# --------------------------------------------------------------------------- #
# The dispatch discriminator itself (trace.py:_in_tracing_dispatch_activity).
# This is the one line preventing a cross-worker handle leak inside START_SPAN,
# so it gets exercised directly with a faked activity.info() -- and against the
# enum's own .value, so it also fails if TracingActivityName ever drifts from
# the strings hardcoded in trace.py.
# --------------------------------------------------------------------------- #
def test_dispatch_discriminator_true_for_start_and_end_span(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(temporal_activity, "in_activity", lambda: True)
    for name in (TracingActivityName.START_SPAN, TracingActivityName.END_SPAN):
        # activity_type round-trips as the plain string value through protobuf.
        monkeypatch.setattr(temporal_activity, "info", lambda n=name: SimpleNamespace(activity_type=n.value))
        assert trace_mod._in_tracing_dispatch_activity() is True, name


def test_dispatch_discriminator_false_for_business_activity(monkeypatch: pytest.MonkeyPatch) -> None:
    # A real agent-turn activity (e.g. process_mortgage_turn) is NOT a dispatch
    # activity -> it must take the per-step wrapper branch, not Option-A tagging.
    monkeypatch.setattr(temporal_activity, "in_activity", lambda: True)
    monkeypatch.setattr(temporal_activity, "info", lambda: SimpleNamespace(activity_type="process_mortgage_turn"))
    assert trace_mod._in_tracing_dispatch_activity() is False


def test_dispatch_discriminator_false_when_not_in_activity(monkeypatch: pytest.MonkeyPatch) -> None:
    # Guard short-circuits on in_activity()==False; info() (here a dispatch value)
    # must never be consulted, else the sync path would be misclassified.
    monkeypatch.setattr(temporal_activity, "in_activity", lambda: False)
    monkeypatch.setattr(temporal_activity, "info", lambda: SimpleNamespace(activity_type="start-span"))
    assert trace_mod._in_tracing_dispatch_activity() is False


def test_in_temporal_activity_tracks_in_activity(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(temporal_activity, "in_activity", lambda: True)
    assert trace_mod._in_temporal_activity() is True
    monkeypatch.setattr(temporal_activity, "in_activity", lambda: False)
    assert trace_mod._in_temporal_activity() is False
