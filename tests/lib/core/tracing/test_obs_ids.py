from __future__ import annotations

import sys
import types

import pytest

from agentex.lib.core.tracing import obs_ids
from agentex.lib.core.tracing.obs_ids import get_obs_mode, obs_correlation


class TestGetObsMode:
    @pytest.mark.parametrize(
        "raw, expected",
        [
            (None, "dd_only"),        # unset
            ("", "dd_only"),          # empty
            ("dd_only", "dd_only"),
            ("lgtm", "lgtm"),
            ("LGTM", "lgtm"),         # case-insensitive
            ("  lgtm  ", "lgtm"),     # trimmed
            ("dual", "dd_only"),      # removed mode -> safe degrade
            ("garbage", "dd_only"),   # unrecognized -> safe degrade
        ],
    )
    def test_mode_resolution(self, monkeypatch, raw, expected):
        if raw is None:
            monkeypatch.delenv("SGP_OBS_MODE", raising=False)
        else:
            monkeypatch.setenv("SGP_OBS_MODE", raw)
        assert get_obs_mode() == expected


class TestObsCorrelation:
    def test_lgtm_mode_reads_otel_and_emits_underscored_keys(self, monkeypatch):
        monkeypatch.setenv("SGP_OBS_MODE", "lgtm")
        monkeypatch.setattr(obs_ids, "_lgtm_ids", lambda: ("otel_trace", "otel_span"))
        # In lgtm mode ddtrace must NOT be consulted.
        monkeypatch.setattr(
            obs_ids, "_ddtrace_ids", lambda: pytest.fail("ddtrace read in lgtm mode")
        )

        assert obs_correlation() == {
            "obs_trace_id": "otel_trace",
            "obs_span_id": "otel_span",
        }

    def test_dd_only_mode_reads_ddtrace(self, monkeypatch):
        monkeypatch.setenv("SGP_OBS_MODE", "dd_only")
        monkeypatch.setattr(obs_ids, "_ddtrace_ids", lambda: ("dd_trace", "dd_span"))
        monkeypatch.setattr(
            obs_ids, "_lgtm_ids", lambda: pytest.fail("otel read in dd_only mode")
        )

        assert obs_correlation() == {
            "obs_trace_id": "dd_trace",
            "obs_span_id": "dd_span",
        }

    def test_stale_dual_degrades_to_ddtrace(self, monkeypatch):
        """A leftover SGP_OBS_MODE=dual must behave as dd_only, not read OTel."""
        monkeypatch.setenv("SGP_OBS_MODE", "dual")
        monkeypatch.setattr(obs_ids, "_ddtrace_ids", lambda: ("dd_trace", "dd_span"))
        monkeypatch.setattr(
            obs_ids, "_lgtm_ids", lambda: pytest.fail("otel read for stale dual mode")
        )

        assert obs_correlation() == {
            "obs_trace_id": "dd_trace",
            "obs_span_id": "dd_span",
        }

    def test_no_active_context_returns_empty(self, monkeypatch):
        monkeypatch.delenv("SGP_OBS_MODE", raising=False)  # dd_only
        monkeypatch.setattr(obs_ids, "_ddtrace_ids", lambda: None)

        assert obs_correlation() == {}

    def test_resolver_exception_is_swallowed(self, monkeypatch):
        """A misbehaving tracer must not propagate out of obs_correlation."""
        monkeypatch.delenv("SGP_OBS_MODE", raising=False)  # dd_only

        def boom():
            raise RuntimeError("tracer blew up")

        monkeypatch.setattr(obs_ids, "_ddtrace_ids", boom)
        assert obs_correlation() == {}


class TestIdFormatting:
    """Pin the W3C hex shape (32-hex trace, 16-hex span) of the resolvers."""

    def test_ddtrace_ids_formats_w3c_hex(self, monkeypatch):
        ctx = types.SimpleNamespace(trace_id=0xABC, span_id=0xFF)
        tracer = types.SimpleNamespace(current_trace_context=lambda: ctx)
        fake_ddtrace = types.ModuleType("ddtrace")
        fake_trace = types.ModuleType("ddtrace.trace")
        fake_trace.tracer = tracer
        monkeypatch.setitem(sys.modules, "ddtrace", fake_ddtrace)
        monkeypatch.setitem(sys.modules, "ddtrace.trace", fake_trace)

        trace_id, span_id = obs_ids._ddtrace_ids()
        assert trace_id == "00000000000000000000000000000abc"
        assert span_id == "000000000000000000ff"[-16:]  # 16-hex
        assert len(trace_id) == 32 and len(span_id) == 16

    def test_lgtm_ids_formats_w3c_hex(self, monkeypatch):
        span_ctx = types.SimpleNamespace(trace_id=0xABC, span_id=0xFF, is_valid=True)
        current_span = types.SimpleNamespace(get_span_context=lambda: span_ctx)
        fake_trace_mod = types.SimpleNamespace(get_current_span=lambda: current_span)
        fake_otel = types.ModuleType("opentelemetry")
        fake_otel.trace = fake_trace_mod
        monkeypatch.setitem(sys.modules, "opentelemetry", fake_otel)

        trace_id, span_id = obs_ids._lgtm_ids()
        assert trace_id == "00000000000000000000000000000abc"
        assert len(trace_id) == 32 and len(span_id) == 16

    def test_ddtrace_ids_none_when_no_context(self, monkeypatch):
        tracer = types.SimpleNamespace(current_trace_context=lambda: None)
        fake_ddtrace = types.ModuleType("ddtrace")
        fake_trace = types.ModuleType("ddtrace.trace")
        fake_trace.tracer = tracer
        monkeypatch.setitem(sys.modules, "ddtrace", fake_ddtrace)
        monkeypatch.setitem(sys.modules, "ddtrace.trace", fake_trace)

        assert obs_ids._ddtrace_ids() is None
