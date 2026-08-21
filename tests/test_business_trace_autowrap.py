"""BaseACPServer auto-applies sgp-obs @business_trace to handlers, fail-open and
version-tolerant (no-op when the installed sgp-obs predates business_trace)."""

import sys
import types

from agentex.lib.sdk.fastacp.base.base_acp_server import BaseACPServer


def test_noop_when_sgp_obs_lacks_business_trace(monkeypatch):
    # sgp-obs too old (no business_trace) -> import fails -> handler returned unchanged
    monkeypatch.setitem(sys.modules, "sgp_obs.traces", None)

    def handler(params):
        return "ok"

    assert BaseACPServer._with_business_trace(handler, lambda p: p.task.id) is handler


def test_applies_business_trace_and_passes_id_getter(monkeypatch):
    calls: dict[str, object] = {}

    fake = types.ModuleType("sgp_obs.traces")

    def business_trace(*, business_trace_id):
        calls["getter"] = business_trace_id

        def deco(fn):
            def wrapped(*a, **k):
                return ("wrapped", fn(*a, **k))

            return wrapped

        return deco

    fake.business_trace = business_trace  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "sgp_obs.traces", fake)

    def handler(params):
        return "ok"

    wrapped = BaseACPServer._with_business_trace(handler, lambda p: p.task.id)
    assert wrapped is not handler
    assert wrapped(None) == ("wrapped", "ok")
    # the id resolver threads through to business_trace
    params = types.SimpleNamespace(task=types.SimpleNamespace(id="T-9"))
    assert calls["getter"](params) == "T-9"


def test_fail_open_when_decorator_raises(monkeypatch):
    fake = types.ModuleType("sgp_obs.traces")

    def business_trace(*, business_trace_id):
        raise RuntimeError("boom")

    fake.business_trace = business_trace  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "sgp_obs.traces", fake)

    def handler(params):
        return "ok"

    # a decorator that blows up must not break handler registration
    assert BaseACPServer._with_business_trace(handler, lambda p: p.task.id) is handler
