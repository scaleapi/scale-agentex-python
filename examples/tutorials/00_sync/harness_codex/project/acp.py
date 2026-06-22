"""Sync ACP handler for the Codex CLI harness tutorial.

Demonstrates the ``convert_codex_to_agentex_events`` tap + ``CodexTurn`` +
``UnifiedEmitter`` for a sync (HTTP-yield) ACP agent.

The handler:
1. Spawns ``codex exec --json`` as a LOCAL asyncio subprocess (no sandbox).
   This is correct for tutorials and local development; production isolation
   is handled by the golden agent's Scale sandbox at
   ``teams/sgp/agents/golden_agent/project/harness/providers/codex.py``.
2. Wraps the stdout line stream in a ``CodexTurn``.
3. Delivers every canonical ``StreamTaskMessage*`` event via
   ``UnifiedEmitter.yield_turn``, which traces + yields each event back to
   the HTTP caller in one pass.

Live runs require:
- ``codex`` CLI on PATH  (``npm install -g @openai/codex``)
- ``OPENAI_API_KEY`` set in the environment
"""

from __future__ import annotations

import os
import time
import asyncio
from typing import AsyncGenerator
from collections.abc import AsyncIterator

from dotenv import load_dotenv

load_dotenv()

import agentex.lib.adk as adk
from agentex.lib.adk import CodexTurn
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

MODEL = os.environ.get("CODEX_MODEL", "o4-mini")


async def _spawn_codex(model: str) -> asyncio.subprocess.Process:
    """Spawn ``codex exec --json`` locally and return the live process.

    Injection seam: tests replace this function with a fake that returns a
    mock process whose stdout yields pre-recorded event lines.

    The flags mirror the golden agent (codex.py in the golden agent repo):
      --json                      machine-readable newline-delimited events
      --skip-git-repo-check       safe to run outside a git repo
      --dangerously-bypass-approvals-and-sandbox
                                  skip interactive approval prompts in a
                                  non-interactive (server) context
      --model <model>             which OpenAI model to use

    The caller writes the prompt to stdin after the process starts, then
    closes stdin so codex knows input is complete.
    """
    cmd = [
        "codex",
        "exec",
        "--json",
        "--skip-git-repo-check",
        "--dangerously-bypass-approvals-and-sandbox",
        "--model",
        model,
        "-",  # read prompt from stdin
    ]
    return await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env={**os.environ},
    )


async def _process_stdout(process: asyncio.subprocess.Process) -> AsyncIterator[str]:
    """Yield newline-delimited JSON lines from the process stdout."""
    assert process.stdout is not None
    buffer = ""
    while True:
        chunk = await process.stdout.read(4096)
        if not chunk:
            break
        buffer += chunk.decode("utf-8", errors="replace")
        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            line = line.strip()
            if line:
                yield line
    if buffer.strip():
        yield buffer.strip()


@acp.on_message_send
async def handle_message_send(
    params: SendMessageParams,
) -> TaskMessageContent | list[TaskMessageContent] | AsyncGenerator[TaskMessageUpdate, None]:
    """Handle each message by running ``codex exec`` locally and streaming events."""
    task_id = params.task.id
    user_message = params.content.content
    logger.info("Processing message for task %s", task_id)

    start_ms = int(time.monotonic() * 1000)

    async with adk.tracing.span(
        trace_id=task_id,
        task_id=task_id,
        name="message",
        input={"message": user_message},
        data={"__span_type__": "AGENT_WORKFLOW"},
    ) as turn_span:
        process = await _spawn_codex(MODEL)

        # Write prompt to stdin then close it so codex knows input is done.
        assert process.stdin is not None
        process.stdin.write(user_message.encode("utf-8"))
        await process.stdin.drain()
        process.stdin.close()

        turn = CodexTurn(
            events=_process_stdout(process),
            model=MODEL,
        )

        emitter = UnifiedEmitter(
            task_id=task_id,
            trace_id=task_id,
            parent_span_id=turn_span.id if turn_span else None,
        )

        async for event in emitter.yield_turn(turn):
            yield event

        await process.wait()

        # Record the real wall-clock duration AFTER streaming completes; setting
        # it before the stream ran would capture only subprocess spawn overhead.
        turn.duration_ms = int(time.monotonic() * 1000) - start_ms

        if turn_span:
            usage = turn.usage()
            turn_span.output = {
                "model": usage.model,
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
            }
