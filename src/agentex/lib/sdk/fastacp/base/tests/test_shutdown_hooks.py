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
from agentex.lib.core.tracing.tracing_processor_manager import (
    shutdown_sync_tracing_processors,
)


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
    async def test_every_processor_is_flushed(self, monkeypatch):
        a, b = _Processor(), _Processor()
        _patch_processors(monkeypatch, [a, b])
        await shutdown_sync_tracing_processors()
        assert (a.calls, b.calls) == (1, 1)

    async def test_one_failure_does_not_stop_the_others(self, monkeypatch):
        """A processor that hangs or raises must not strand the spans held by the
        ones after it in the list."""
        bad, good = _Processor(explode=True), _Processor()
        _patch_processors(monkeypatch, [bad, good])
        await shutdown_sync_tracing_processors()
        assert good.calls == 1

    async def test_no_processors_is_a_no_op(self, monkeypatch):
        _patch_processors(monkeypatch, [])
        await shutdown_sync_tracing_processors()  # must not raise

    async def test_an_unimportable_manager_does_not_fail_shutdown(self, monkeypatch):
        """Nothing here may stop the pod from shutting down."""
        import builtins

        real_import = builtins.__import__

        def blocked(name, *args, **kwargs):
            if "tracing_processor_manager" in name:
                raise ImportError("boom")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", blocked)
        await shutdown_sync_tracing_processors()  # must not raise

    def test_the_lifespan_calls_it(self):
        """Pin the wiring, not just the helper: a drain nothing calls is worthless."""
        import inspect

        source = inspect.getsource(base_acp_server.BaseACPServer.get_lifespan_function)
        assert "shutdown_sync_tracing_processors()" in source
        assert "shutdown_sgp_obs()" in source


class TestTheDrainIsBounded:
    """`SGPSyncTracingProcessor.shutdown` does a BLOCKING HTTP flush with retries. If
    the drain waited on it inline and without a limit, a slow or unreachable collector
    would burn the pod's whole termination grace period and the OTel flush that runs
    after it would never happen — trading a few business spans for all of the OTel ones.
    """

    async def test_a_stalled_processor_does_not_hang_shutdown(self, monkeypatch):
        import time
        import asyncio

        class Stalled:
            def shutdown(self):
                time.sleep(2)  # blocking, like a retrying HTTP flush

        _patch_processors(monkeypatch, [Stalled()])
        started = asyncio.get_running_loop().time()
        await shutdown_sync_tracing_processors(budget_s=0.25)
        elapsed = asyncio.get_running_loop().time() - started
        assert elapsed < 1, f"drain took {elapsed:.1f}s against a 0.25s budget"

    async def test_the_budget_is_shared_so_a_stall_cannot_starve_the_rest(self, monkeypatch):
        """A shared deadline means the drain as a whole is bounded, not each processor
        separately — N stalled processors must not cost N * budget."""
        import time
        import asyncio

        class Stalled:
            def shutdown(self):
                time.sleep(2)

        _patch_processors(monkeypatch, [Stalled(), Stalled(), Stalled()])
        started = asyncio.get_running_loop().time()
        await shutdown_sync_tracing_processors(budget_s=0.25)
        elapsed = asyncio.get_running_loop().time() - started
        assert elapsed < 1, f"drain took {elapsed:.1f}s for 3 stalled processors"

    async def test_it_does_not_block_the_event_loop(self, monkeypatch):
        """The flush must run off-loop: other lifespan work has to keep progressing
        while a processor is stuck."""
        import time
        import asyncio

        class Stalled:
            def shutdown(self):
                time.sleep(2)

        _patch_processors(monkeypatch, [Stalled()])
        ticks = 0

        async def heartbeat():
            nonlocal ticks
            while True:
                await asyncio.sleep(0.01)
                ticks += 1

        beat = asyncio.create_task(heartbeat())
        await shutdown_sync_tracing_processors(budget_s=0.25)
        beat.cancel()
        assert ticks > 0, "the event loop was blocked during the drain"


class TestTheTemporalWorkerIsWiredToo:
    """A Temporal agent runs its model calls in the worker process, which never
    constructs a BaseACPServer. Without its own init the documented environment leaves
    that process — the one doing the interesting work — completely unwired.
    """

    def test_the_worker_inits_and_drains(self):
        import inspect

        from agentex.lib.core.temporal.workers.worker import AgentexWorker

        source = inspect.getsource(AgentexWorker.run)
        assert "init_sgp_obs()" in source
        assert "shutdown_sgp_obs()" in source
        assert "shutdown_sync_tracing_processors()" in source

    def test_the_worker_does_not_pass_an_app(self):
        """There is no ASGI application in the worker process. The health-check server
        is aiohttp, which sgp-obs' ASGI middleware does not apply to, so passing it
        would be wrong rather than merely useless."""
        import inspect

        from agentex.lib.core.temporal.workers.worker import AgentexWorker

        source = inspect.getsource(AgentexWorker.run)
        assert "init_sgp_obs(app=" not in source
