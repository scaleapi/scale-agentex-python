from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock

from agentex.lib.core.tracing import obs_span
from agentex.lib.core.tracing.trace import Trace


# --------------------------------------------------------------------------- #
# Fake OTel (lgtm) and fake ddtrace (dd_only) SDKs injected via sys.modules.
# --------------------------------------------------------------------------- #
class _FakeSpanContext:
    def __init__(self, trace_id: int, span_id: int, is_valid: bool = True):
        self.trace_id = trace_id
        self.span_id = span_id
        self.is_valid = is_valid


class _FakeOtelSpan:
    def __init__(self, name: str, trace_id: int, span_id: int):
        self.name = name
        self._ctx = _FakeSpanContext(trace_id, span_id)
        self.ended = False
        self.attributes: dict = {}

    def set_attribute(self, key, value):
        self.attributes[key] = value

    def get_span_context(self):
        return self._ctx

    def end(self):
        self.ended = True


def _install_fake_otel(monkeypatch, *, trace_id=0xABC, span_id=0xFF):
    record: dict = {"span": None, "attached": [], "detached": []}

    def start_span(name):
        span = _FakeOtelSpan(name, trace_id, span_id)
        record["span"] = span
        return span

    tracer = types.SimpleNamespace(start_span=start_span)
    fake_trace = types.SimpleNamespace(
        get_tracer=lambda _name: tracer,
        set_span_in_context=lambda span: {"span": span},
    )
    fake_context = types.SimpleNamespace(
        attach=lambda ctx: record["attached"].append(ctx) or object(),
        detach=lambda token: record["detached"].append(token),
    )
    fake_otel = types.ModuleType("opentelemetry")
    fake_otel.trace = fake_trace
    fake_otel.context = fake_context
    monkeypatch.setitem(sys.modules, "opentelemetry", fake_otel)
    return record


class _FakeDDSpan:
    def __init__(self, name: str, trace_id: int, span_id: int):
        self.name = name
        self.trace_id = trace_id
        self.span_id = span_id
        self.finished = False
        self.tags: dict = {}

    def set_tag(self, key, value):
        self.tags[key] = value

    def finish(self):
        self.finished = True


def _install_fake_ddtrace(monkeypatch, *, active=True, trace_id=0xABC, span_id=0xFF):
    record: dict = {"span": None, "started": []}

    def start_span(name, activate=False):
        span = _FakeDDSpan(name, trace_id, span_id)
        record["span"] = span
        record["started"].append((name, activate))
        return span

    tracer = types.SimpleNamespace(
        current_trace_context=lambda: (object() if active else None),
        start_span=start_span,
    )
    fake_ddtrace = types.ModuleType("ddtrace")
    fake_trace = types.ModuleType("ddtrace.trace")
    fake_trace.tracer = tracer
    monkeypatch.setitem(sys.modules, "ddtrace", fake_ddtrace)
    monkeypatch.setitem(sys.modules, "ddtrace.trace", fake_trace)
    return record


# --------------------------------------------------------------------------- #
# lgtm -> OTel wrapper
# --------------------------------------------------------------------------- #
class TestOtelWrapper:
    def test_lgtm_opens_named_span_and_reads_its_ids(self, monkeypatch):
        monkeypatch.setenv("SGP_OBS_MODE", "lgtm")
        record = _install_fake_otel(monkeypatch, trace_id=0xABC, span_id=0xFF)

        handle = obs_span.open_obs_span(
            "rocket.tool.fetch", business_span_id="bspan-1", business_trace_id="btrace-1"
        )

        assert handle is not None
        assert record["span"].name == "rocket.tool.fetch"   # named for the step
        assert len(record["attached"]) == 1                 # made active
        assert handle.correlation == {
            "obs_trace_id": "00000000000000000000000000000abc",
            "obs_span_id": "000000000000000000ff"[-16:],
        }
        # reverse tag: business ids stamped on the obs span
        assert record["span"].attributes == {
            "agentex.business_span_id": "bspan-1",
            "agentex.business_trace_id": "btrace-1",
        }

    def test_invalid_span_context_yields_empty_correlation(self, monkeypatch):
        monkeypatch.setenv("SGP_OBS_MODE", "lgtm")
        _install_fake_otel(monkeypatch)

        def start_span(name):
            span = _FakeOtelSpan(name, 0, 0)
            span._ctx = _FakeSpanContext(0, 0, is_valid=False)
            return span

        sys.modules["opentelemetry"].trace.get_tracer = lambda _n: types.SimpleNamespace(
            start_span=start_span
        )
        handle = obs_span.open_obs_span("step")
        assert handle is not None
        assert handle.correlation == {}

    def test_close_detaches_and_ends(self, monkeypatch):
        monkeypatch.setenv("SGP_OBS_MODE", "lgtm")
        record = _install_fake_otel(monkeypatch)
        handle = obs_span.open_obs_span("step")

        obs_span.close_obs_span(handle)

        assert record["span"].ended is True
        assert len(record["detached"]) == 1

    def test_close_none_is_noop(self):
        obs_span.close_obs_span(None)  # must not raise


# --------------------------------------------------------------------------- #
# dd_only -> ddtrace wrapper (only when a request trace is active)
# --------------------------------------------------------------------------- #
class TestDdtraceWrapper:
    def test_dd_only_with_active_ctx_opens_named_span(self, monkeypatch):
        monkeypatch.setenv("SGP_OBS_MODE", "dd_only")
        record = _install_fake_ddtrace(monkeypatch, active=True, trace_id=0xABC, span_id=0xFF)

        handle = obs_span.open_obs_span(
            "rocket.tool.fetch", business_span_id="bspan-9", business_trace_id="btrace-9"
        )

        assert handle is not None
        assert record["span"].name == "rocket.tool.fetch"
        assert record["started"] == [("rocket.tool.fetch", True)]  # activated
        assert handle.correlation == {
            "obs_trace_id": "00000000000000000000000000000abc",
            "obs_span_id": "000000000000000000ff"[-16:],
        }
        # reverse tag on the ddtrace span
        assert record["span"].tags == {
            "agentex.business_span_id": "bspan-9",
            "agentex.business_trace_id": "btrace-9",
        }

        obs_span.close_obs_span(handle)
        assert record["span"].finished is True

    def test_dd_only_without_active_ctx_returns_none(self, monkeypatch):
        """Bare-uvicorn / no ddtrace-run: nothing active -> no orphan wrapper."""
        monkeypatch.setenv("SGP_OBS_MODE", "dd_only")
        record = _install_fake_ddtrace(monkeypatch, active=False)

        assert obs_span.open_obs_span("step") is None
        assert record["span"] is None  # never created a span


# --------------------------------------------------------------------------- #
# End-to-end through Trace.start_span / end_span
# --------------------------------------------------------------------------- #
class TestTraceIntegration:
    def test_lgtm_business_span_tagged_with_wrapper_ids(self, monkeypatch):
        monkeypatch.setenv("SGP_OBS_MODE", "lgtm")
        record = _install_fake_otel(monkeypatch, trace_id=0x111, span_id=0x222)

        trace = Trace(processors=[], client=MagicMock(), trace_id="task-run-1")
        span = trace.start_span(name="chat_completion")

        assert record["span"].name == "chat_completion"     # dedicated named span
        assert span.data["obs_trace_id"] == "00000000000000000000000000000111"
        assert span.data["obs_span_id"] == "0000000000000222"
        assert span.trace_id == "task-run-1"                # business id unchanged
        assert span.id in trace._obs_handles
        # bidirectional: the obs span carries the business ids (reverse tag),
        # and the business span carries the obs ids (forward edge).
        assert record["span"].attributes == {
            "agentex.business_span_id": span.id,
            "agentex.business_trace_id": "task-run-1",
        }

        trace.end_span(span)
        assert record["span"].ended is True
        assert span.id not in trace._obs_handles

    def test_dd_only_business_span_tagged_via_ddtrace(self, monkeypatch):
        monkeypatch.setenv("SGP_OBS_MODE", "dd_only")
        record = _install_fake_ddtrace(monkeypatch, active=True, trace_id=0x111, span_id=0x222)

        trace = Trace(processors=[], client=MagicMock(), trace_id="task-run-2")
        span = trace.start_span(name="get_state")

        assert record["span"].name == "get_state"
        assert span.data["obs_trace_id"] == "00000000000000000000000000000111"
        assert span.data["obs_span_id"] == "0000000000000222"
        assert record["span"].tags == {
            "agentex.business_span_id": span.id,
            "agentex.business_trace_id": "task-run-2",
        }

        trace.end_span(span)
        assert record["span"].finished is True
        assert span.id not in trace._obs_handles

    def test_dd_only_no_ctx_falls_back_to_ambient(self, monkeypatch):
        monkeypatch.setenv("SGP_OBS_MODE", "dd_only")
        _install_fake_ddtrace(monkeypatch, active=False)
        monkeypatch.setattr("agentex.lib.core.tracing.trace.obs_correlation", lambda: {})

        trace = Trace(processors=[], client=MagicMock(), trace_id="task-run-3")
        span = trace.start_span(name="get_state")

        assert trace._obs_handles == {}   # no wrapper opened
        assert span.data is None          # nothing tagged
        trace.end_span(span)              # must not raise


# --------------------------------------------------------------------------- #
# Non-interference: the two backends are mutually exclusive per mode.
# --------------------------------------------------------------------------- #
class TestNonInterference:
    def test_lgtm_touches_only_otel(self, monkeypatch):
        monkeypatch.setenv("SGP_OBS_MODE", "lgtm")
        otel = _install_fake_otel(monkeypatch)
        dd = _install_fake_ddtrace(monkeypatch, active=True)

        obs_span.open_obs_span("step")

        assert otel["span"] is not None    # OTel wrapper opened
        assert dd["span"] is None          # ddtrace never touched

    def test_dd_only_touches_only_ddtrace(self, monkeypatch):
        monkeypatch.setenv("SGP_OBS_MODE", "dd_only")
        otel = _install_fake_otel(monkeypatch)
        dd = _install_fake_ddtrace(monkeypatch, active=True)

        obs_span.open_obs_span("step")

        assert dd["span"] is not None      # ddtrace wrapper opened
        assert otel["span"] is None        # OTel never touched


# --------------------------------------------------------------------------- #
# No-op when unconfigured, and never fails the app call.
# --------------------------------------------------------------------------- #
class TestNeverFails:
    def test_lgtm_no_otel_installed_returns_none(self, monkeypatch):
        monkeypatch.setenv("SGP_OBS_MODE", "lgtm")
        monkeypatch.setitem(sys.modules, "opentelemetry", None)  # import -> ImportError
        assert obs_span.open_obs_span("step") is None

    def test_dd_only_no_ddtrace_installed_returns_none(self, monkeypatch):
        monkeypatch.setenv("SGP_OBS_MODE", "dd_only")
        monkeypatch.setitem(sys.modules, "ddtrace.trace", None)  # import -> ImportError
        assert obs_span.open_obs_span("step") is None

    def test_backend_exception_is_swallowed(self, monkeypatch):
        monkeypatch.setenv("SGP_OBS_MODE", "lgtm")
        _install_fake_otel(monkeypatch)

        def boom(_name):
            raise RuntimeError("tracer blew up")

        sys.modules["opentelemetry"].trace.get_tracer = boom
        assert obs_span.open_obs_span("step") is None   # inner guard

    def test_top_level_guard_swallows_get_mode_error(self, monkeypatch):
        # Even if mode resolution itself raises, open_obs_span must not.
        monkeypatch.setattr(obs_span, "get_obs_mode", lambda: (_ for _ in ()).throw(RuntimeError()))
        assert obs_span.open_obs_span("step") is None

    def test_close_swallows_closer_error(self):
        handle = obs_span.ObsSpanHandle({}, lambda: (_ for _ in ()).throw(RuntimeError()))
        obs_span.close_obs_span(handle)  # must not raise

    def test_unconfigured_lgtm_yields_usable_span_no_raise(self, monkeypatch):
        # lgtm requested but OTel not installed: the REAL open_obs_span returns
        # None, obs_correlation() returns {} (also no tracer) -> the business
        # span is created and fully usable, and nothing raised.
        monkeypatch.setenv("SGP_OBS_MODE", "lgtm")
        monkeypatch.setitem(sys.modules, "opentelemetry", None)

        trace = Trace(processors=[], client=MagicMock(), trace_id="task-run-4")
        span = trace.start_span(name="safe")

        assert span.trace_id == "task-run-4"
        assert trace._obs_handles == {}   # no wrapper
        trace.end_span(span)              # must not raise


def _install_fake_otel_sequence(monkeypatch, *, trace_id: int, first_span_id: int):
    """Fake OTel whose wrapper spans all share ``trace_id`` (children of the one
    turn/request obs trace) but get sequential distinct span ids."""
    state: dict = {"next": first_span_id, "spans": []}

    def start_span(name):
        sid = state["next"]
        state["next"] += 1
        span = _FakeOtelSpan(name, trace_id, sid)
        state["spans"].append(span)
        return span

    tracer = types.SimpleNamespace(start_span=start_span)
    fake_trace = types.SimpleNamespace(
        get_tracer=lambda _name: tracer,
        set_span_in_context=lambda span: {"span": span},
    )
    fake_context = types.SimpleNamespace(
        attach=lambda ctx: object(),
        detach=lambda token: None,
    )
    fake_otel = types.ModuleType("opentelemetry")
    fake_otel.trace = fake_trace
    fake_otel.context = fake_context
    monkeypatch.setitem(sys.modules, "opentelemetry", fake_otel)
    return state


class TestTurn2Example:
    """Maps the 3-turn mortgage example, Turn 2 (obs trace B):

        get_state        -> wrapper wB1  -> obs_span_id = wB1
        retrieve_docs    -> wrapper wB2  -> obs_span_id = wB2
        chat_completion  -> wrapper wB3  -> obs_span_id = wB3
        create_message   -> wrapper wB4  -> obs_span_id = wB4

    Each step opens its OWN dedicated span named for the step; all four share the
    one turn obs trace B, but obs_span_id is distinct per step (not all rB).
    """

    def test_turn2_each_step_gets_distinct_named_wrapper_under_trace_B(self, monkeypatch):
        monkeypatch.setenv("SGP_OBS_MODE", "lgtm")
        # Turn 2's request obs trace = B (0xB); wrappers get span ids 0xB1.. .
        state = _install_fake_otel_sequence(monkeypatch, trace_id=0xB, first_span_id=0xB1)

        run_id = "task-run-mortgage"  # business trace_id = the run/task id
        trace = Trace(processors=[], client=MagicMock(), trace_id=run_id)

        steps = ["get_state", "retrieve_docs", "chat_completion", "create_message"]
        business = []
        for step in steps:
            with trace.span(name=step) as s:
                business.append(s)

        obs_trace_B = format(0xB, "032x")
        expected_obs_span = [format(sid, "016x") for sid in (0xB1, 0xB2, 0xB3, 0xB4)]

        # one dedicated wrapper per step, named for the step, in order
        assert [w.name for w in state["spans"]] == steps

        for biz, wrapper, exp_span in zip(business, state["spans"], expected_obs_span):
            # forward edge: business span carries the wrapper's ids
            assert biz.data["obs_trace_id"] == obs_trace_B      # all under trace B
            assert biz.data["obs_span_id"] == exp_span          # distinct wBn
            # reverse tag: wrapper carries the business ids
            assert wrapper.attributes == {
                "agentex.business_span_id": biz.id,
                "agentex.business_trace_id": run_id,
            }

        # the whole point of the fix: obs_span_id is DISTINCT per step ...
        obs_span_ids = [b.data["obs_span_id"] for b in business]
        assert obs_span_ids == expected_obs_span
        assert len(set(obs_span_ids)) == 4
        # ... while all four share the single turn obs trace B
        assert {b.data["obs_trace_id"] for b in business} == {obs_trace_B}
        # business trace stays the run/task id, not the obs trace
        assert {b.trace_id for b in business} == {run_id}
