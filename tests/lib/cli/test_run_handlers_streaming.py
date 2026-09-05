"""Tests for run_handlers output streaming.

stream_process_output is the only reader of a child's stdout pipe. If it stops
reading, the pipe fills and the child blocks forever inside write(), which
presents as a silent freeze with no traceback. These tests pin the behaviour
that prevents that: a line the reader cannot handle is skipped, not fatal.
"""

from __future__ import annotations

import sys
import asyncio

from agentex.lib.cli.handlers.run_handlers import (
    SUBPROCESS_STREAM_LIMIT,
    stream_process_output,
)

# Emits a line over the reader's limit, then enough further output to more than
# fill a 64 KiB pipe. If the reader stops draining, the child cannot finish its
# writes and never exits.
CHILD_SCRIPT = """
import sys
print("before")
print("X" * {oversized})
for i in range(2000):
    print("after", i, "y" * 60)
print("done")
"""


async def _drain(limit: int, oversized: int) -> int | None:
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-c",
        CHILD_SCRIPT.format(oversized=oversized),
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


async def test_oversized_line_is_skipped_without_stalling_the_child() -> None:
    """A line past the reader's limit is dropped and streaming continues.

    Before this was handled per line, readline() raised, the loop exited, and the
    child deadlocked on a full pipe. The child reaching exit is the assertion.
    """
    limit = 64 * 1024
    returncode = await _drain(limit=limit, oversized=limit + 16_000)

    assert returncode == 0, "child did not exit: the reader stopped draining its pipe"


async def test_large_line_within_limit_is_streamed() -> None:
    """A line larger than asyncio's 64 KiB default still streams under our limit."""
    returncode = await _drain(limit=SUBPROCESS_STREAM_LIMIT, oversized=82_000)

    assert returncode == 0


async def test_subprocess_stream_limit_exceeds_asyncio_default() -> None:
    """The whole point of the constant: asyncio's default is what breaks readline()."""
    assert SUBPROCESS_STREAM_LIMIT > 64 * 1024
