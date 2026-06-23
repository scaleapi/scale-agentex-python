"""Async (base) ACP handler for the Codex CLI harness tutorial.

Demonstrates the ``convert_codex_to_agentex_events`` tap + ``CodexTurn`` +
``UnifiedEmitter`` for an async (Redis-streaming) ACP agent without Temporal.

The handler:
1. Spawns ``codex exec --json`` as a LOCAL asyncio subprocess (no sandbox).
   This is correct for tutorials and local development; production isolation
   is handled by the golden agent's Scale sandbox at
   ``teams/sgp/agents/golden_agent/project/harness/providers/codex.py``.
2. Wraps the stdout line stream in a ``CodexTurn``.
3. Delivers every canonical ``StreamTaskMessage*`` event to Redis via
   ``UnifiedEmitter.auto_send_turn``, so the UI receives tokens in real time.
4. Multi-turn memory is persisted via ``adk.state``.

Live runs require:
- ``codex`` CLI on PATH  (``npm install -g @openai/codex``)
- ``OPENAI_API_KEY`` set in the environment
"""

from __future__ import annotations

import os
import time
import codecs
import asyncio
from collections.abc import AsyncIterator

from dotenv import load_dotenv

load_dotenv()

import agentex.lib.adk as adk
from agentex.lib.adk import CodexTurn
from agentex.lib.types.acp import SendEventParams, CancelTaskParams, CreateTaskParams
from agentex.lib.core.harness import UnifiedEmitter
from agentex.lib.types.fastacp import AsyncACPConfig
from agentex.lib.types.tracing import SGPTracingProcessorConfig
from agentex.lib.utils.logging import make_logger
from agentex.lib.utils.model_utils import BaseModel
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

MODEL = os.environ.get("CODEX_MODEL", "o4-mini")


class ConversationState(BaseModel):
    """Per-task conversation state persisted via ``adk.state``.

    We store the codex session/thread ID so subsequent turns can resume the
    same codex session via ``codex exec resume <thread_id>``.
    """

    codex_thread_id: str | None = None
    turn_number: int = 0


async def _spawn_codex(
    model: str,
    thread_id: str | None = None,
) -> asyncio.subprocess.Process:
    """Spawn ``codex exec --json`` locally and return the live process.

    Injection seam: tests replace this function with a fake that returns a
    mock process whose stdout yields pre-recorded event lines.

    When ``thread_id`` is provided the subcommand becomes
    ``codex exec ... resume <thread_id> -`` so codex continues the prior
    conversation thread.

    The caller writes the prompt to stdin after the process starts, then
    closes stdin so codex knows input is complete.
    """
    base_flags = [
        "--json",
        "--skip-git-repo-check",
        "--dangerously-bypass-approvals-and-sandbox",
        "--model",
        model,
    ]

    if thread_id:
        cmd = ["codex", "exec", *base_flags, "resume", thread_id, "-"]
    else:
        cmd = ["codex", "exec", *base_flags, "-"]

    return await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        # Discard stderr: codex --json writes events to stdout; its stderr is
        # progress/debug noise. Capturing it with PIPE but never reading it
        # would deadlock once codex fills the OS pipe buffer (~64 KB).
        stderr=asyncio.subprocess.DEVNULL,
        env={**os.environ},
    )


async def _process_stdout(process: asyncio.subprocess.Process) -> AsyncIterator[str]:
    """Yield newline-delimited JSON lines from the process stdout.

    Uses an incremental UTF-8 decoder so a multibyte character split across two
    4 KB reads is decoded correctly instead of being corrupted at the boundary.
    """
    assert process.stdout is not None
    decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
    buffer = ""
    while True:
        chunk = await process.stdout.read(4096)
        if not chunk:
            break
        buffer += decoder.decode(chunk)
        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            line = line.strip()
            if line:
                yield line
    buffer += decoder.decode(b"", final=True)
    if buffer.strip():
        yield buffer.strip()


@acp.on_task_create
async def handle_task_create(params: CreateTaskParams):
    """Initialize per-task state on task creation."""
    logger.info("Task created: %s", params.task.id)
    await adk.state.create(
        task_id=params.task.id,
        agent_id=params.agent.id,
        state=ConversationState(),
    )


@acp.on_task_event_send
async def handle_task_event_send(params: SendEventParams):
    """Handle each user message: spawn codex, stream events, save thread ID."""
    task_id = params.task.id
    agent_id = params.agent.id
    user_message = params.event.content.content

    logger.info("Processing message for task %s", task_id)

    await adk.messages.create(task_id=task_id, content=params.event.content)

    task_state = await adk.state.get_by_task_and_agent(task_id=task_id, agent_id=agent_id)
    if task_state is None:
        state = ConversationState()
        task_state = await adk.state.create(task_id=task_id, agent_id=agent_id, state=state)
    else:
        state = ConversationState.model_validate(task_state.state)

    state.turn_number += 1

    async with adk.tracing.span(
        trace_id=task_id,
        task_id=task_id,
        name=f"Turn {state.turn_number}",
        input={"message": user_message},
        data={"__span_type__": "AGENT_WORKFLOW"},
    ) as turn_span:
        start_ms = int(time.monotonic() * 1000)

        process = await _spawn_codex(MODEL, thread_id=state.codex_thread_id)

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

        result = await emitter.auto_send_turn(turn)

        await process.wait()

        # Record the real wall-clock duration AFTER streaming completes; setting
        # it before the stream ran would capture only subprocess spawn overhead.
        turn.duration_ms = int(time.monotonic() * 1000) - start_ms

        # Persist the new thread ID so subsequent turns resume the same session.
        usage = turn.usage()
        if usage.model:
            # usage() is valid now that the stream is exhausted
            pass
        # Persist the codex session id (public accessor; valid post-stream) so the
        # next turn resumes the same session.
        if turn.session_id:
            state.codex_thread_id = turn.session_id

        await adk.state.update(
            state_id=task_state.id,
            task_id=task_id,
            agent_id=agent_id,
            state=state,
        )

        if turn_span:
            turn_span.output = {
                "final_text": result.final_text,
                "model": usage.model,
            }


@acp.on_task_cancel
async def handle_task_canceled(params: CancelTaskParams):
    logger.info("Task canceled: %s", params.task.id)
