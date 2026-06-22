"""Temporal workflow for the Claude Code tutorial.

Holds conversation state (session_id for multi-turn resume) durably across
crashes. Each user message triggers ``on_task_event_send``, which spawns the
Claude Code CLI locally as an asyncio subprocess, wraps the stdout line
stream in ``ClaudeCodeTurn``, and delivers the turn via
``UnifiedEmitter.auto_send_turn`` (the async Redis push path).

Note on subprocess inside Temporal
------------------------------------
Temporal activities, not workflow code, should do I/O. However, this tutorial
executes the subprocess directly in the signal handler (workflow code) to keep
the example minimal. For production use, move the subprocess spawn into a
dedicated activity so it benefits from Temporal's retry and timeout guarantees.
See ``examples/tutorials/10_async/10_temporal/030_custom_activities/`` for
the activity pattern.
"""

from __future__ import annotations

import os
import json
import asyncio
from typing import AsyncIterator

from temporalio import workflow

from agentex.lib import adk
from agentex.lib.adk import ClaudeCodeTurn
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


async def _spawn_claude(prompt: str, session_id: str | None = None) -> AsyncIterator[str]:
    """Spawn ``claude -p --output-format stream-json`` locally and yield stdout lines.

    Pass ``session_id`` to resume a previous Claude Code session (multi-turn
    memory via ``-r <session_id>``).

    Injectable seam: tests monkeypatch this with a fake async iterator so no
    real CLI invocation is needed offline.
    """
    cmd = [
        "claude",
        "-p",
        "--output-format",
        "stream-json",
        "--verbose",
    ]
    if session_id:
        cmd.extend(["-r", session_id])

    proc = await asyncio.create_subprocess_exec(
        *cmd,
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


@workflow.defn(name=environment_variables.WORKFLOW_NAME)
class At140ClaudeCodeWorkflow(BaseWorkflow):
    """Temporal workflow that runs Claude Code locally for each user message.

    Persists the Claude Code session_id across turns so the CLI can resume
    the conversation (``-r <session_id>``). Temporal's durable state ensures
    the session_id survives worker crashes.
    """

    def __init__(self):
        super().__init__(display_name=environment_variables.AGENT_NAME)
        self._complete_task = False
        self._turn_number = 0
        # Claude Code session_id for multi-turn resume.
        self._session_id: str | None = None

    @workflow.signal(name=SignalName.RECEIVE_EVENT)
    async def on_task_event_send(self, params: SendEventParams) -> None:
        """Handle a user message: spawn Claude Code and push events to the task stream."""
        self._turn_number += 1
        task_id = params.task.id
        prompt = params.event.content.content
        logger.info("Turn %d for task %s", self._turn_number, task_id)

        await adk.messages.create(task_id=task_id, content=params.event.content)

        async with adk.tracing.span(
            trace_id=task_id,
            task_id=task_id,
            name=f"Turn {self._turn_number}",
            input={"message": prompt},
        ) as span:
            emitter = UnifiedEmitter(
                task_id=task_id,
                trace_id=task_id,
                parent_span_id=span.id if span else None,
            )

            # Use workflow.now() for deterministic timestamps under Temporal replay.
            created_at = workflow.now()

            turn = ClaudeCodeTurn(_spawn_claude(prompt, session_id=self._session_id))
            result = await emitter.auto_send_turn(turn, created_at=created_at)

            # Capture session_id from result envelope to enable resume on next turn.
            # ClaudeCodeTurn.usage() gives us access to the raw result envelope via
            # TurnUsage -- but session_id is not part of TurnUsage. We extract it
            # separately by looking at the turn's internal state post-exhaust.
            if hasattr(turn, "_result_envelope") and turn._result_envelope:
                sid = turn._result_envelope.get("session_id")
                if sid:
                    self._session_id = sid

            if span:
                span.output = {"final_text": result.final_text}

    @workflow.run
    async def on_task_create(self, params: CreateTaskParams) -> str:
        logger.info("Task created: %s", params.task.id)

        await adk.messages.create(
            task_id=params.task.id,
            content=TextContent(
                author="agent",
                content=(
                    f"Task initialized with params:\n{json.dumps(params.params, indent=2)}\n"
                    "Send me a message and I'll run it through Claude Code locally."
                ),
            ),
        )

        await workflow.wait_condition(lambda: self._complete_task, timeout=None)
        return "Task completed"

    @workflow.signal
    async def complete_task_signal(self) -> None:
        logger.info("Received complete_task signal")
        self._complete_task = True
