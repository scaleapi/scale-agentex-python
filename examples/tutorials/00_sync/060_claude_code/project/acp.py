"""ACP handler for the sync Claude Code tutorial.

Spawns ``claude -p --output-format stream-json --verbose`` as a LOCAL
asyncio subprocess (no Scale sandbox -- that is the golden agent's
production concern). Stdout lines are fed into ``ClaudeCodeTurn``, which
wraps ``convert_claude_code_to_agentex_events``. Events are delivered via
``UnifiedEmitter.yield_turn``, the sync HTTP yield path.

Live runs require the ``claude`` CLI to be installed and an
ANTHROPIC_API_KEY (or equivalent credential) to be in the environment.
For offline testing, see ``tests/test_agent_offline.py``, which injects a
fake subprocess.
"""

from __future__ import annotations

import os
import asyncio
from typing import AsyncIterator, AsyncGenerator

from dotenv import load_dotenv

load_dotenv()

import agentex.lib.adk as adk
from agentex.lib.adk import ClaudeCodeTurn
from agentex.lib.types.acp import SendMessageParams
from agentex.lib.core.harness import UnifiedEmitter
from agentex.lib.types.tracing import SGPTracingProcessorConfig
from agentex.lib.utils.logging import make_logger
from agentex.lib.sdk.fastacp.fastacp import FastACP
from agentex.types.task_message_update import TaskMessageUpdate
from agentex.types.task_message_content import TaskMessageContent
from agentex.lib.core.tracing.tracing_processor_manager import add_tracing_processor_config

logger = make_logger(__name__)

add_tracing_processor_config(
    SGPTracingProcessorConfig(
        sgp_api_key=os.environ.get("SGP_API_KEY", ""),
        sgp_account_id=os.environ.get("SGP_ACCOUNT_ID", ""),
        sgp_base_url=os.environ.get("SGP_CLIENT_BASE_URL", ""),
    )
)

acp = FastACP.create(acp_type="sync")


async def _spawn_claude(prompt: str) -> AsyncIterator[str]:
    """Spawn ``claude -p --output-format stream-json`` locally and yield stdout lines.

    This is a seam: tests replace it with a fake async iterator of
    pre-recorded lines so no real CLI invocation is needed offline.
    """
    proc = await asyncio.create_subprocess_exec(
        "claude",
        "-p",
        "--output-format",
        "stream-json",
        "--verbose",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    assert proc.stdout is not None
    assert proc.stdin is not None

    proc.stdin.write(prompt.encode())
    proc.stdin.close()

    # Drain stderr concurrently. With --verbose, Claude Code can write enough to
    # stderr to fill the OS pipe buffer; if we only read stdout, the CLI blocks
    # on its stderr write while we block reading stdout — a deadlock. A
    # background task keeps stderr flowing so stdout never stalls.
    async def _drain_stderr() -> None:
        assert proc.stderr is not None
        async for _ in proc.stderr:
            pass

    stderr_task = asyncio.create_task(_drain_stderr())

    buffer = ""
    async for chunk in proc.stdout:
        buffer += chunk.decode("utf-8", errors="replace")
        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            line = line.strip()
            if line:
                yield line

    if buffer.strip():
        yield buffer.strip()

    await proc.wait()
    await stderr_task


@acp.on_message_send
async def handle_message_send(
    params: SendMessageParams,
) -> TaskMessageContent | list[TaskMessageContent] | AsyncGenerator[TaskMessageUpdate, None]:
    """Handle an incoming message: run Claude Code locally and stream events."""
    task_id = params.task.id
    prompt = params.content.content
    logger.info("Processing message for task %s", task_id)

    async with adk.tracing.span(
        trace_id=task_id,
        task_id=task_id,
        name="message",
        input={"message": prompt},
        data={"__span_type__": "AGENT_WORKFLOW"},
    ) as turn_span:
        emitter = UnifiedEmitter(
            task_id=task_id,
            trace_id=task_id,
            parent_span_id=turn_span.id if turn_span else None,
        )
        turn = ClaudeCodeTurn(_spawn_claude(prompt))
        async for event in emitter.yield_turn(turn):
            yield event
