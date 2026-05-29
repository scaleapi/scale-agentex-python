from __future__ import annotations

import asyncio
import weakref
from unittest.mock import MagicMock, patch

import pytest

# AgentexAsyncTracingProcessor pulls in agentex.lib.adk via
# create_async_agentex_client, which in turn imports pydantic_ai at package
# init.  Skip these tests cleanly when pydantic_ai isn't installed (the SDK
# dev venv state) so collection doesn't error out.
pytest.importorskip(
    "pydantic_ai",
    reason="agentex.lib.adk import chain requires pydantic_ai",
)

# Import the processor module up front so unittest.mock.patch() can resolve
# attributes by string path.  The tracing_processor_manager only loads this
# module lazily, so without this explicit import the patches below would fail
# with AttributeError at __enter__ time.
import agentex.lib.core.tracing.processors.agentex_tracing_processor  # noqa: E402, F401

MODULE = "agentex.lib.core.tracing.processors.agentex_tracing_processor"


def _make_config() -> MagicMock:
    """Empty config — AgentexTracingProcessorConfig is unused by __init__."""
    return MagicMock()


class TestAgentexAsyncTracingProcessor:
    """Coverage for the per-event-loop client cache.  The SGP processor has
    matching tests; mirror them here so a regression in the Agentex side
    (e.g. an accidental refactor that switches back to a plain dict, or
    drops the lazy lookup) does not slip through unnoticed.
    """

    async def test_client_caches_per_event_loop(self):
        """First access builds the client; subsequent accesses in the same
        running loop must return the cached instance.
        """
        with patch(f"{MODULE}.create_async_agentex_client") as mock_factory:
            mock_factory.side_effect = lambda **kwargs: MagicMock()

            from agentex.lib.core.tracing.processors.agentex_tracing_processor import (
                AgentexAsyncTracingProcessor,
            )

            processor = AgentexAsyncTracingProcessor(_make_config())

            # Construction must not eagerly build the client (no running loop
            # guarantee at module import time).
            assert mock_factory.call_count == 0

            c1 = processor.client
            c2 = processor.client
            c3 = processor.client

        assert mock_factory.call_count == 1, (
            f"Expected client to be built once per loop, but "
            f"create_async_agentex_client was called {mock_factory.call_count} times"
        )
        assert c1 is c2 is c3

    async def test_client_keepalive_is_enabled(self):
        """Regression guard: the per-loop client must use keepalive — the
        whole reason for the per-loop cache.  Verify max_keepalive_connections > 0.
        """
        import httpx as _httpx

        captured_limits: list[_httpx.Limits] = []
        original_async_client = _httpx.AsyncClient

        def capture_limits(*args, **kwargs):
            limits = kwargs.get("limits")
            if limits is not None:
                captured_limits.append(limits)
            return original_async_client(*args, **kwargs)

        with patch(f"{MODULE}.create_async_agentex_client") as mock_factory, patch(
            "httpx.AsyncClient", side_effect=capture_limits
        ):
            mock_factory.side_effect = lambda **kwargs: MagicMock()

            from agentex.lib.core.tracing.processors.agentex_tracing_processor import (
                AgentexAsyncTracingProcessor,
            )

            processor = AgentexAsyncTracingProcessor(_make_config())
            _ = processor.client

        assert len(captured_limits) == 1
        max_keepalive = captured_limits[0].max_keepalive_connections
        assert max_keepalive is not None and max_keepalive > 0, (
            f"Agentex async client should have keepalive enabled, got "
            f"max_keepalive_connections={max_keepalive}"
        )

    def test_cache_is_weakkeydict_and_evicts_dead_loops(self):
        """Regression guard for the id()-reuse bug: the per-loop cache must
        be a WeakKeyDictionary so a GC'd loop's entry is evicted.  Otherwise
        a new loop landing at the same memory address would reuse the dead
        loop's client, reintroducing the "bound to a different event loop"
        error the per-loop cache was built to prevent.
        """
        import gc

        with patch(f"{MODULE}.create_async_agentex_client"):
            from agentex.lib.core.tracing.processors.agentex_tracing_processor import (
                AgentexAsyncTracingProcessor,
            )

            processor = AgentexAsyncTracingProcessor(_make_config())

        # Storage type itself: WeakKeyDictionary, not plain dict.
        assert isinstance(processor._clients_by_loop, weakref.WeakKeyDictionary)

        # End-to-end check: insert under a loop, drop the loop, the entry
        # must vanish after GC.
        loop = asyncio.new_event_loop()
        try:
            processor._clients_by_loop[loop] = MagicMock()
            assert len(processor._clients_by_loop) == 1
        finally:
            loop.close()
        del loop
        gc.collect()
        assert len(processor._clients_by_loop) == 0, (
            "WeakKeyDictionary should have evicted the dead loop's entry; "
            "remaining keys would cause stale-client reuse on id() recycling."
        )
