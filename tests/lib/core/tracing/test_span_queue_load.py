"""
Manual load test for the tracing pipeline.

Measures peak queue depth, drain time, and memory under sustained load with
large system prompts — the scenario that causes OOM in K8s.

SKIPPED by default.  Run explicitly with:

    RUN_LOAD_TESTS=1 PYTHONPATH=src python -m pytest \
        tests/lib/core/tracing/test_span_queue_load.py \
        -v -o "addopts=--tb=short" -s

To compare before/after the fix:

    # 1) Baseline (before fix) — checkout the parent commit:
    git stash  # if you have uncommitted changes
    git checkout ced40bb
    RUN_LOAD_TESTS=1 PYTHONPATH=src python -m pytest \
        tests/lib/core/tracing/test_span_queue_load.py \
        -v -o "addopts=--tb=short" -s

    # 2) After fix — return to your branch:
    git checkout -
    git stash pop  # if you stashed
    RUN_LOAD_TESTS=1 PYTHONPATH=src python -m pytest \
        tests/lib/core/tracing/test_span_queue_load.py \
        -v -o "addopts=--tb=short" -s
"""

from __future__ import annotations

import asyncio
import gc
import os
import resource
import sys
import time
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from agentex.types.span import Span
from agentex.lib.core.tracing.span_queue import AsyncSpanQueue
from agentex.lib.core.tracing.trace import AsyncTrace

# ---------------------------------------------------------------------------
# Configuration — tune to match production load profile
# ---------------------------------------------------------------------------
N_SPANS = 10_000
PROMPT_SIZE = 50_000        # 50 KB system prompt per span
PROCESSOR_DELAY_S = 0.005   # 5 ms per processor call (simulates API latency)
REQUEST_INTERVAL_S = 0.0002 # 0.2 ms between requests (~5000 req/s burst)
SAMPLE_INTERVAL = 200       # sample queue depth every N spans


def _make_span(span_id: str | None = None) -> Span:
    return Span(
        id=span_id or str(uuid.uuid4()),
        name="test-span",
        start_time=datetime.now(UTC),
        trace_id="trace-1",
    )


@pytest.mark.skipif(
    not os.environ.get("RUN_LOAD_TESTS"),
    reason="Load test — run with RUN_LOAD_TESTS=1",
)
class TestSpanQueueLoad:
    async def test_sustained_load(self):
        """
        Push 10,000 spans with 50KB system prompts through the tracing pipeline
        at a steady rate while the drain loop runs concurrently.

        Prints a full report with peak queue depth, timing, and memory.
        Compare the output between old code (ced40bb) and the fix branch.
        """
        peak_queue_size = 0
        queue_samples: list[tuple[int, int]] = []

        async def slow_start(span: Span) -> None:
            await asyncio.sleep(PROCESSOR_DELAY_S)

        async def slow_end(span: Span) -> None:
            await asyncio.sleep(PROCESSOR_DELAY_S)

        proc = AsyncMock()
        proc.on_span_start = AsyncMock(side_effect=slow_start)
        proc.on_span_end = AsyncMock(side_effect=slow_end)

        queue = AsyncSpanQueue()
        trace = AsyncTrace(
            processors=[proc],
            client=MagicMock(),
            trace_id="load-test",
            span_queue=queue,
        )

        gc.collect()

        if sys.platform == "darwin":
            rss_to_mb = 1 / 1024 / 1024  # bytes
        else:
            rss_to_mb = 1 / 1024  # KB

        rss_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * rss_to_mb
        t_start = time.monotonic()

        # ---- Enqueue phase (steady stream) ----
        for i in range(N_SPANS):
            input_data = {
                "system_prompt": f"You are agent #{i}. " + "x" * PROMPT_SIZE,
                "messages": [{"role": "user", "content": f"Request {i}"}],
            }
            span = await trace.start_span(f"llm-call-{i}", input=input_data)
            span.output = {
                "response": f"Reply {i}",
                "usage": {"prompt_tokens": 500, "completion_tokens": 100},
            }
            await trace.end_span(span)

            # Yield to event loop so the drain task can run between requests.
            await asyncio.sleep(REQUEST_INTERVAL_S)

            qs = queue._queue.qsize()
            if qs > peak_queue_size:
                peak_queue_size = qs
            if i % SAMPLE_INTERVAL == 0:
                queue_samples.append((i, qs))

        t_enqueue = time.monotonic()

        # ---- Drain phase (flush remaining) ----
        await queue.shutdown(timeout=300)
        t_end = time.monotonic()

        rss_after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * rss_to_mb

        enqueue_s = t_enqueue - t_start
        drain_s = t_end - t_enqueue
        total_s = t_end - t_start

        # ---- Report ----
        print()
        print(f"{'=' * 60}")
        print(f" Load Test: {N_SPANS:,} spans x {PROMPT_SIZE // 1000}KB prompt")
        print(f" Processor delay: {PROCESSOR_DELAY_S * 1000:.0f}ms"
              f" | Request interval: {REQUEST_INTERVAL_S * 1000:.1f}ms")
        print(f"{'=' * 60}")
        print(f" Peak queue depth:  {peak_queue_size:>10,} items")
        print(f" Enqueue time:      {enqueue_s:>10.2f} s")
        print(f" Drain time:        {drain_s:>10.2f} s")
        print(f" Total time:        {total_s:>10.2f} s")
        print(f" RSS before:        {rss_before:>10.1f} MB")
        print(f" RSS after:         {rss_after:>10.1f} MB")
        print(f" RSS delta:         {rss_after - rss_before:>10.1f} MB")
        print(f"{'=' * 60}")
        print()
        print(" Queue depth over time:")
        for idx, depth in queue_samples:
            bar = "#" * (depth // 200) if depth > 0 else "."
            print(f"   span {idx:>6,}: {depth:>6,} items  {bar}")
        print()

        # Soft assertion — the test is informational, but flag extreme backup
        assert peak_queue_size < N_SPANS * 2, (
            f"Queue never drained during load — peak was {peak_queue_size} "
            f"(total items enqueued: {N_SPANS * 2})"
        )

    async def test_growing_context_chatbot(self):
        """
        Simulate concurrent chatbot conversations where each turn adds to the
        message history.  Each LLM call span carries the FULL conversation
        (system prompt + all prior messages), so input size grows linearly
        per turn and total memory is O(N^2) across turns.

        This is the worst-case scenario for queue memory: later turns produce
        spans with much larger inputs than early turns.

        Config below: 50 concurrent conversations × 40 turns each = 2,000
        total spans.  By turn 40, each span carries ~50KB system prompt +
        ~80KB of message history.
        """
        N_CONVERSATIONS = 50
        TURNS_PER_CONV = 40
        SYS_PROMPT_SIZE = 50_000       # 50 KB system prompt
        MSG_SIZE = 2_000               # 2 KB per user/assistant message
        DELAY = 0.005                  # 5 ms processor latency
        INTERVAL = 0.0002              # 0.2 ms between turns

        peak_queue_size = 0
        total_spans = N_CONVERSATIONS * TURNS_PER_CONV
        queue_samples: list[tuple[int, int, int]] = []  # (span_idx, queue_depth, input_kb)
        span_count = 0

        async def slow_start(span: Span) -> None:
            await asyncio.sleep(DELAY)

        async def slow_end(span: Span) -> None:
            await asyncio.sleep(DELAY)

        proc = AsyncMock()
        proc.on_span_start = AsyncMock(side_effect=slow_start)
        proc.on_span_end = AsyncMock(side_effect=slow_end)

        queue = AsyncSpanQueue()
        trace = AsyncTrace(
            processors=[proc],
            client=MagicMock(),
            trace_id="chatbot-load",
            span_queue=queue,
        )

        gc.collect()

        if sys.platform == "darwin":
            rss_to_mb = 1 / 1024 / 1024
        else:
            rss_to_mb = 1 / 1024

        rss_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * rss_to_mb
        t_start = time.monotonic()

        # Build N_CONVERSATIONS, each accumulating message history
        conversations: list[list[dict]] = [[] for _ in range(N_CONVERSATIONS)]
        system_prompt = "You are a helpful assistant. " + "x" * SYS_PROMPT_SIZE

        for turn in range(TURNS_PER_CONV):
            for conv_id in range(N_CONVERSATIONS):
                # User sends a message
                conversations[conv_id].append({
                    "role": "user",
                    "content": f"[conv={conv_id} turn={turn}] " + "u" * MSG_SIZE,
                })

                # LLM call span — carries full conversation history
                input_data = {
                    "system_prompt": system_prompt,
                    "messages": list(conversations[conv_id]),  # copy of full history
                }
                input_kb = len(str(input_data)) // 1024

                span = await trace.start_span(
                    f"llm-conv{conv_id}-turn{turn}",
                    input=input_data,
                )
                assistant_reply = f"[reply conv={conv_id} turn={turn}] " + "a" * MSG_SIZE
                span.output = {"response": assistant_reply}
                await trace.end_span(span)

                # Assistant reply added to history
                conversations[conv_id].append({
                    "role": "assistant",
                    "content": assistant_reply,
                })

                span_count += 1
                await asyncio.sleep(INTERVAL)

                qs = queue._queue.qsize()
                if qs > peak_queue_size:
                    peak_queue_size = qs
                if span_count % 100 == 0:
                    queue_samples.append((span_count, qs, input_kb))

        t_enqueue = time.monotonic()
        await queue.shutdown(timeout=300)
        t_end = time.monotonic()

        rss_after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * rss_to_mb
        enqueue_s = t_enqueue - t_start
        drain_s = t_end - t_enqueue
        total_s = t_end - t_start

        # ---- Report ----
        print()
        print(f"{'=' * 60}")
        print(f" Chatbot Load Test: {N_CONVERSATIONS} convos x"
              f" {TURNS_PER_CONV} turns = {total_spans:,} spans")
        print(f" System prompt: {SYS_PROMPT_SIZE // 1000}KB"
              f" | Message size: {MSG_SIZE // 1000}KB"
              f" | Processor delay: {DELAY * 1000:.0f}ms")
        print(f"{'=' * 60}")
        print(f" Peak queue depth:  {peak_queue_size:>10,} items")
        print(f" Enqueue time:      {enqueue_s:>10.2f} s")
        print(f" Drain time:        {drain_s:>10.2f} s")
        print(f" Total time:        {total_s:>10.2f} s")
        print(f" RSS before:        {rss_before:>10.1f} MB")
        print(f" RSS after:         {rss_after:>10.1f} MB")
        print(f" RSS delta:         {rss_after - rss_before:>10.1f} MB")
        print(f"{'=' * 60}")
        print()
        print(" Queue depth & per-span input size over time:")
        print(f"   {'span':>8}  {'queue':>8}  {'input':>8}")
        for idx, depth, ikb in queue_samples:
            q_bar = "#" * (depth // 100) if depth > 0 else "."
            print(f"   {idx:>7,}  {depth:>7,}  {ikb:>6}KB  {q_bar}")
        print()

        assert peak_queue_size < total_spans * 2, (
            f"Queue never drained — peak was {peak_queue_size} "
            f"(total items enqueued: {total_spans * 2})"
        )
