"""ACP handler for the async Claude Code tutorial.

Spawns ``claude -p --output-format stream-json --verbose`` as a LOCAL
asyncio subprocess (no Scale sandbox -- that is the golden agent's
production concern). Stdout lines are fed into ``ClaudeCodeTurn``. Events
are delivered via ``UnifiedEmitter.auto_send_turn``, the async Redis push
path.

Live runs require the ``claude`` CLI to be installed and an
ANTHROPIC_API_KEY (or equivalent credential) in the environment.
For offline testing, see ``tests/test_agent_offline.py``.
"""

from __future__ import annotations

import os
import asyncio
from typing import AsyncIterator

from dotenv import load_dotenv

load_dotenv()

import agentex.lib.adk as adk
from agentex.lib.adk import ClaudeCodeTurn
from agentex.lib.types.acp import SendEventParams, CancelTaskParams, CreateTaskParams
from agentex.lib.core.harness import UnifiedEmitter
from agentex.lib.types.fastacp import AsyncACPConfig
from agentex.lib.types.tracing import SGPTracingProcessorConfig
from agentex.lib.utils.logging import make_logger
from agentex.lib.sdk.fastacp.fastacp import FastACP
from agentex.lib.core.tracing.tracing_processor_manager import add_tracing_processor_config

logger = make_logger(__name__)

add_tracing_processor_config(
    SGPTracingProcessorConfig(
        sgp_api_key=os.environ.get("SGP_API_KEY", ""),
        sgp_account_id=os.environ.get("SGP_ACCOUNT_ID", ""),
        sgp_base_url=os.environ.get("SGP_CLIENT_BASE_URL", ""),
    )
)

acp = FastACP.create(
    acp_type="async",
    config=AsyncACPConfig(type="base"),
)


async def _spawn_claude(prompt: str) -> AsyncIterator[str]:
    """Spawn ``claude -p --output-format stream-json`` locally and yield stdout lines.

    Injectable seam: tests monkeypatch this with a fake async iterator of
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


@acp.on_task_create
async def handle_task_create(params: CreateTaskParams):
    logger.info("Task created: %s", params.task.id)


@acp.on_task_event_send
async def handle_task_event_send(params: SendEventParams):
    """Handle a user message: spawn Claude Code locally and push events to the task stream."""
    task_id = params.task.id
    prompt = params.event.content.content
    logger.info("Processing message for task %s", task_id)

    await adk.messages.create(task_id=task_id, content=params.event.content)

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
        result = await emitter.auto_send_turn(turn)
        if turn_span:
            turn_span.output = {"final_text": result.final_text}


@acp.on_task_cancel
async def handle_task_canceled(params: CancelTaskParams):
    logger.info("Task canceled: %s", params.task.id)
