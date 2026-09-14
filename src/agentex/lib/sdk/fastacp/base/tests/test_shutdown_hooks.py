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

    async def test_an_unreadable_processor_list_does_not_fail_shutdown(self, monkeypatch):
        """Nothing here may stop the pod from shutting down.

        This used to block the import of ``tracing_processor_manager``, which tested
        nothing once the drain moved INTO that module: it reads
        ``get_sync_tracing_processors`` as a module global, so the import never runs and
        the ``except`` branch was never reached. Make the lookup itself raise instead."""
        import agentex.lib.core.tracing.tracing_processor_manager as mgr

        def boom():
            raise RuntimeError("processor registry unavailable")

        monkeypatch.setattr(mgr, "get_sync_tracing_processors", boom)
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


class TestConcurrencyAndProcessExit:
    """Two properties the budget only really has if these hold."""

    async def test_a_fast_processor_finishes_even_when_another_stalls(self, monkeypatch):
        """Flushes start concurrently under ONE shared deadline. Draining them in
        sequence let the first stalled processor spend the whole budget, so every
        processor after it was skipped even when it would have returned instantly."""
        import time

        class Stalled:
            def shutdown(self):
                time.sleep(2)

        class Fast:
            def __init__(self):
                self.flushed = False

            def shutdown(self):
                self.flushed = True

        fast = Fast()
        # Stalled FIRST: in a sequential drain it would eat the budget and `fast`
        # would never be asked.
        _patch_processors(monkeypatch, [Stalled(), fast])
        await shutdown_sync_tracing_processors(budget_s=0.5)
        assert fast.flushed, "a fast processor was starved by a stalled one"

    def test_a_stalled_flush_does_not_delay_process_exit(self):
        """The property the deadline actually promises, and the one it did NOT have.

        `asyncio.wait_for` stops awaiting a thread; it cannot stop the thread. And
        `asyncio.run` joins the default executor on the way out (as does a private
        ThreadPoolExecutor, via its atexit hook), so a timed-out `asyncio.to_thread`
        flush left the process blocked on the very export the budget was meant to
        escape — measured at 10.0s against a 0.25s budget. Daemon threads are abandoned
        at interpreter exit, which is what the budget promises.

        A subprocess, because this is about interpreter shutdown: it cannot be observed
        from inside the test process.
        """
        import os
        import sys
        import time
        import textwrap
        import subprocess
        from pathlib import Path

        # tests/base/fastacp/sdk/lib/agentex/src -> parents[6] is the src root.
        src = Path(__file__).resolve().parents[6]
        program = textwrap.dedent(
            """
            import asyncio, sys, time
            from agentex.lib.core.tracing.tracing_processor_manager import (
                shutdown_sync_tracing_processors,
            )
            import agentex.lib.core.tracing.tracing_processor_manager as mgr

            class Stalled:
                def shutdown(self):
                    time.sleep(30)

            mgr.get_sync_tracing_processors = lambda: [Stalled()]
            asyncio.run(shutdown_sync_tracing_processors(budget_s=0.25))
            """
        )
        started = time.monotonic()
        proc = subprocess.run(
            [sys.executable, "-c", program],
            capture_output=True,
            text=True,
            timeout=30,
            # Inherit the environment: replacing it wholesale breaks the
            # interpreter's own bootstrap before the test can run.
            env={**os.environ, "PYTHONPATH": str(src)},
        )
        elapsed = time.monotonic() - started
        assert proc.returncode == 0, proc.stderr[-2000:]
        assert elapsed < 10, (
            f"process took {elapsed:.1f}s to exit with a 30s stalled flush and a "
            "0.25s budget; the flush thread is blocking interpreter shutdown"
        )
