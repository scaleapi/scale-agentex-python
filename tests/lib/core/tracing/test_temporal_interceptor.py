"""Unit tests for the Temporal OTel trace-interceptor wiring.

Verifies the interceptor is on by default, the opt-out env flag, and the safe
no-op fallback when temporalio's OpenTelemetry contrib isn't importable.
"""

import sys

import pytest

from agentex.lib.core.tracing import temporal as temporal_tracing


class TestTemporalTraceInterceptor:
    def test_enabled_by_default(self, monkeypatch):
        monkeypatch.delenv("AGENTEX_TEMPORAL_TRACE_INTERCEPTOR_ENABLED", raising=False)
        assert temporal_tracing.temporal_trace_interceptor_enabled() is True

        interceptors = temporal_tracing.temporal_tracing_interceptors()
        assert len(interceptors) == 1
        # temporalio's first-party OTel interceptor
        assert type(interceptors[0]).__name__ == "TracingInterceptor"

    @pytest.mark.parametrize("value", ["false", "0", "no", "off", "FALSE", "Off"])
    def test_disabled_via_env(self, monkeypatch, value):
        monkeypatch.setenv("AGENTEX_TEMPORAL_TRACE_INTERCEPTOR_ENABLED", value)
        assert temporal_tracing.temporal_trace_interceptor_enabled() is False
        assert temporal_tracing.temporal_tracing_interceptors() == []

    @pytest.mark.parametrize("value", ["true", "1", "yes", "TRUE", "anything"])
    def test_enabled_for_non_falsy_values(self, monkeypatch, value):
        monkeypatch.setenv("AGENTEX_TEMPORAL_TRACE_INTERCEPTOR_ENABLED", value)
        assert temporal_tracing.temporal_trace_interceptor_enabled() is True

    def test_no_op_when_contrib_unimportable(self, monkeypatch):
        # Enabled, but temporalio's OTel contrib not importable -> [] (never raises),
        # so default-on can't break a worker that lacks the contrib.
        monkeypatch.delenv("AGENTEX_TEMPORAL_TRACE_INTERCEPTOR_ENABLED", raising=False)
        monkeypatch.setitem(sys.modules, "temporalio.contrib.opentelemetry", None)
        assert temporal_tracing.temporal_tracing_interceptors() == []
