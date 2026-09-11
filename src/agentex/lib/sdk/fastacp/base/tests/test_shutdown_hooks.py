"""Tests for the ACP lifespan's shutdown drains.

``shutdown_default_span_queue`` covers the async span path. The SYNC tracing
processors keep their own queue, and nothing in the SDK ever shut them down, so a
sync ACP agent dropped whatever business spans were still queued when the pod
stopped. That is worse than the spans themselves: the business span is what an obs
span's ``agentex.business_trace_id`` resolves to, so losing it breaks the pivot from
Tempo back to the SGP store.
"""

from __future__ import annotations

from agentex.lib.sdk.fastacp.base import base_acp_server
from agentex.lib.sdk.fastacp.base.base_acp_server import _shutdown_sync_tracing_processors


class _Processor:
    def __init__(self, explode: bool = False) -> None:
        self.calls = 0
        self._explode = explode

    def shutdown(self) -> None:
        self.calls += 1
        if self._explode:
            raise RuntimeError("flush timed out")


def _patch_processors(monkeypatch, processors):
    import agentex.lib.core.tracing.tracing_processor_manager as mgr

    monkeypatch.setattr(mgr, "get_sync_tracing_processors", lambda: processors)


class TestSyncProcessorDrain:
    def test_every_processor_is_flushed(self, monkeypatch):
        a, b = _Processor(), _Processor()
        _patch_processors(monkeypatch, [a, b])
        _shutdown_sync_tracing_processors()
        assert (a.calls, b.calls) == (1, 1)

    def test_one_failure_does_not_stop_the_others(self, monkeypatch):
        """A processor that hangs or raises must not strand the spans held by the
        ones after it in the list."""
        bad, good = _Processor(explode=True), _Processor()
        _patch_processors(monkeypatch, [bad, good])
        _shutdown_sync_tracing_processors()
        assert good.calls == 1

    def test_no_processors_is_a_no_op(self, monkeypatch):
        _patch_processors(monkeypatch, [])
        _shutdown_sync_tracing_processors()  # must not raise

    def test_an_unimportable_manager_does_not_fail_shutdown(self, monkeypatch):
        """Nothing here may stop the pod from shutting down."""
        import builtins

        real_import = builtins.__import__

        def blocked(name, *args, **kwargs):
            if "tracing_processor_manager" in name:
                raise ImportError("boom")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", blocked)
        _shutdown_sync_tracing_processors()  # must not raise

    def test_the_lifespan_calls_it(self):
        """Pin the wiring, not just the helper: a drain nothing calls is worthless."""
        import inspect

        source = inspect.getsource(base_acp_server.BaseACPServer.get_lifespan_function)
        assert "_shutdown_sync_tracing_processors()" in source
        assert "shutdown_sgp_obs()" in source
