"""Temporal workflow for the Codex harness tutorial.

Demonstrates the ``convert_codex_to_agentex_events`` tap + ``CodexTurn`` +
``UnifiedEmitter`` for a Temporal-durable ACP agent.

KEY CONCEPTS DEMONSTRATED:
- Spawning ``codex exec --json`` as a local asyncio subprocess inside a
  Temporal workflow signal handler. The subprocess itself is NOT a Temporal
  activity — for a tutorial that is fine. Production agents would wrap the
  spawn in a Temporal activity for durability + observability.
- Wrapping the stdout line stream in a ``CodexTurn``.
- Delivering events via ``UnifiedEmitter.auto_send_turn``, which pushes
  ``StreamTaskMessage*`` events to Redis so the UI sees tokens in real time.
- Passing ``created_at=workflow.now()`` for deterministic timestamps under
  Temporal replay (required for Temporal-safe delivery).
- Persisting the codex thread ID on the workflow instance itself — Temporal's
  workflow state is durable, so no external ``adk.state`` round-trip is needed.

NOTE: Subprocess spawning is safe inside a Temporal signal handler because
Temporal does NOT replay signal handler bodies (only ``@workflow.run`` is
subject to replay determinism constraints). Signal handlers run in the live
process after the initial replay is complete.
"""

from __future__ import annotations

import os
import asyncio
from collections.abc import AsyncIterator

from temporalio import workflow

from agentex.lib import adk
from agentex.lib.adk import CodexTurn
from agentex.lib.types.acp import SendEventParams, CreateTaskParams
from agentex.lib.core.harness import UnifiedEmitter
from agentex.lib.types.tracing import SGPTracingProcessorConfig
from agentex.lib.utils.logging import make_logger
from agentex.types.text_content import TextContent
from agentex.lib.environment_variables import EnvironmentVariables
from agentex.lib.core.temporal.types.workflow import SignalName
from agentex.lib.core.temporal.workflows.workflow import BaseWorkflow
from agentex.lib.core.tracing.tracing_processor_manager import add_tracing_processor_config

add_tracing_processor_config(
    SGPTracingProcessorConfig(
        sgp_api_key=os.environ.get("SGP_API_KEY", ""),
        sgp_account_id=os.environ.get("SGP_ACCOUNT_ID", ""),
        sgp_base_url=os.environ.get("SGP_CLIENT_BASE_URL", ""),
    )
)

environment_variables = EnvironmentVariables.refresh()

if environment_variables.WORKFLOW_NAME is None:
    raise ValueError("Environment variable WORKFLOW_NAME is not set")
if environment_variables.AGENT_NAME is None:
    raise ValueError("Environment variable AGENT_NAME is not set")

logger = make_logger(__name__)

MODEL = os.environ.get("CODEX_MODEL", "o4-mini")


async def _spawn_codex(
    model: str,
    thread_id: str | None = None,
) -> asyncio.subprocess.Process:
    """Spawn ``codex exec --json`` locally and return the live process.

    Injection seam: tests replace this function with a fake that returns a
    mock process whose stdout yields pre-recorded event lines.

    NOTE: This function must NOT be called during Temporal workflow replay
    (Temporal's determinism guard would flag it as a non-deterministic side
    effect). Signal handler bodies are safe: Temporal does not replay them.

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


@workflow.defn(name=environment_variables.WORKFLOW_NAME)
class AtHarnessCodexWorkflow(BaseWorkflow):
    """Long-running Temporal workflow that runs codex exec for each turn.

    Conversation state (codex thread ID + turn counter) is kept on the
    workflow instance. Temporal's durable replay reconstructs this state if
    the worker crashes, so no external ``adk.state`` round-trip is needed.
    """

    def __init__(self):
        super().__init__(display_name=environment_variables.AGENT_NAME)
        self._complete_task = False
        self._turn_number = 0
        self._codex_thread_id: str | None = None

    @workflow.signal(name=SignalName.RECEIVE_EVENT)
    async def on_task_event_send(self, params: SendEventParams) -> None:
        """Handle a new user message: spawn codex, stream events via UnifiedEmitter."""
        logger.info("Received task event: %s", params.task.id)
        self._turn_number += 1

        await adk.messages.create(task_id=params.task.id, content=params.event.content)

        user_message = params.event.content.content

        async with adk.tracing.span(
            trace_id=params.task.id,
            task_id=params.task.id,
            name=f"Turn {self._turn_number}",
            input={"message": user_message},
        ) as span:
            process = await _spawn_codex(MODEL, thread_id=self._codex_thread_id)

            assert process.stdin is not None
            process.stdin.write(user_message.encode("utf-8"))
            await process.stdin.drain()
            process.stdin.close()

            turn = CodexTurn(
                events=_process_stdout(process),
                model=MODEL,
            )

            emitter = UnifiedEmitter(
                task_id=params.task.id,
                trace_id=params.task.id,
                parent_span_id=span.id if span else None,
            )

            # Pass workflow.now() so Temporal replay stamps messages with a
            # deterministic timestamp from the workflow clock, not wall time.
            result = await emitter.auto_send_turn(turn, created_at=workflow.now())

            await process.wait()

            if turn.session_id:
                self._codex_thread_id = turn.session_id

            if span:
                span.output = {
                    "final_text": result.final_text,
                    "model": turn.usage().model,
                }

    @workflow.run
    async def on_task_create(self, params: CreateTaskParams) -> str:
        """Workflow entry point — keep the conversation alive for incoming signals."""
        logger.info("Task created: %s", params.task.id)

        await adk.messages.create(
            task_id=params.task.id,
            content=TextContent(
                author="agent",
                content=(
                    f"Task initialized.\n"
                    f"Send me a message and I'll run codex (local subprocess) "
                    f"to answer, streaming events via the unified harness surface."
                ),
            ),
        )

        await workflow.wait_condition(lambda: self._complete_task, timeout=None)
        return "Task completed"

    @workflow.signal
    async def complete_task_signal(self) -> None:
        """Graceful workflow shutdown signal."""
        logger.info("Received complete_task signal")
        self._complete_task = True
