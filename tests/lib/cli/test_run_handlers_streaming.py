"""Tests for run_handlers output streaming.

stream_process_output is the only reader of a child's stdout pipe. If it stops
reading, the pipe fills and the child blocks forever inside write(), which
presents as a silent freeze with no traceback. These tests pin the behaviour
that prevents that: a line the reader cannot handle is skipped, not fatal.
"""

from __future__ import annotations

import sys
import asyncio
from typing import Any

import pytest

from agentex.lib.cli.debug import DebugMode, DebugConfig
from agentex.lib.cli.handlers import run_handlers
from agentex.lib.cli.debug.debug_handlers import (
    start_acp_server_debug,
    start_temporal_worker_debug,
)
from agentex.lib.cli.handlers.run_handlers import (
    SUBPROCESS_STREAM_LIMIT,
    start_acp_server,
    start_temporal_worker,
    stream_process_output,
)

# Emits a line of MARKER over the reader's limit, then enough further output to
# more than fill a 64 KiB pipe. If the reader stops draining, the child cannot
# finish its writes and never exits.
MARKER = "X"

CHILD_SCRIPT = """
print("before")
print("{marker}" * {oversized})
for i in range(2000):
    print("after", i, "y" * 60)
print("done")
"""


async def _drain(limit: int, oversized: int) -> int | None:
    """Run the child under stream_process_output. None means it never exited."""
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-c",
        CHILD_SCRIPT.format(marker=MARKER, oversized=oversized),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        limit=limit,
    )
    streamer = asyncio.create_task(stream_process_output(process, "TEST"))
    try:
        await asyncio.wait_for(asyncio.gather(streamer, process.wait()), timeout=60)
    except TimeoutError:
        process.kill()
        await process.wait()
        return None
    return process.returncode


async def test_oversized_line_is_skipped_without_stalling_the_child(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A line past the reader's limit is dropped, and streaming continues.

    Before this was handled per line, readline() raised, the loop exited, and the
    child deadlocked on a full pipe. The child reaching exit is the assertion.
    """
    limit = 64 * 1024
    oversized = limit + 16_000

    returncode = await _drain(limit=limit, oversized=oversized)
    out = capsys.readouterr().out

    assert returncode == 0, "child did not exit: the reader stopped draining its pipe"
    # The offending line is gone, but everything after it still streamed.
    assert out.count(MARKER) == 0
    assert "done" in out


async def test_large_line_within_the_limit_is_streamed_in_full(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A line over asyncio's 64 KiB default still reaches the console under our limit.

    Counts marker characters rather than matching the line, because rich wraps
    long output across terminal-width lines.
    """
    oversized = 82_000

    returncode = await _drain(limit=SUBPROCESS_STREAM_LIMIT, oversized=oversized)
    out = capsys.readouterr().out

    assert returncode == 0
    assert out.count(MARKER) == oversized, "the large line was dropped rather than streamed"


class _AlwaysFailingReader:
    """A reader whose readline() raises without consuming anything.

    The dangerous shape: skipping it makes no progress, so an unbounded retry
    would spin at 100% CPU while still not draining the pipe.
    """

    def __init__(self) -> None:
        self.attempts = 0

    async def readline(self) -> bytes:
        self.attempts += 1
        raise ValueError("unreadable, and nothing was consumed")


class _FakeProcess:
    def __init__(self, stdout: Any) -> None:
        self.stdout = stdout


async def test_repeated_unreadable_lines_give_up_instead_of_spinning() -> None:
    """A ValueError that consumes nothing must not loop forever."""
    reader = _AlwaysFailingReader()

    await asyncio.wait_for(
        stream_process_output(_FakeProcess(reader), "TEST"), timeout=30
    )

    assert reader.attempts == run_handlers.MAX_CONSECUTIVE_READ_ERRORS + 1


async def test_cancellation_is_not_swallowed() -> None:
    """The auto-reload path cancels these tasks, so cancel must propagate.

    CancelledError derives from BaseException, so the outer `except Exception`
    does not catch it. This pins that, since swallowing it would hang restarts.
    """

    class _NeverReturns:
        async def readline(self) -> bytes:
            await asyncio.sleep(3600)
            return b""

    task = asyncio.create_task(stream_process_output(_FakeProcess(_NeverReturns()), "TEST"))
    await asyncio.sleep(0)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task


async def test_every_spawn_uses_the_larger_limit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    """Every spawn must pass limit=, including the debug ones.

    A subprocess left on asyncio's default overruns far more easily, and enough
    consecutive overruns exhaust MAX_CONSECUTIVE_READ_ERRORS and stop the reader
    draining, which is the deadlock the bound exists to avoid.
    """
    seen: list[int | None] = []

    async def fake_exec(*_args: Any, **kwargs: Any) -> None:
        seen.append(kwargs.get("limit"))

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    monkeypatch.setattr(run_handlers, "calculate_uvicorn_target_for_local", lambda *_: "project.acp")

    await start_acp_server(tmp_path / "acp.py", 8000, {}, tmp_path)
    await start_temporal_worker(tmp_path / "run_worker.py", {}, tmp_path)

    # BOTH, since each helper refuses unless its own mode is enabled.
    debug_config = DebugConfig(
        enabled=True, mode=DebugMode.BOTH, port=5678, wait_for_attach=False, auto_port=False
    )
    await start_acp_server_debug(tmp_path / "acp.py", 8000, {}, debug_config)
    await start_temporal_worker_debug(tmp_path / "run_worker.py", {}, debug_config)

    assert seen == [SUBPROCESS_STREAM_LIMIT] * 4, f"a spawn is missing limit=: {seen}"
    assert SUBPROCESS_STREAM_LIMIT > 64 * 1024, "asyncio's default is what breaks readline()"
