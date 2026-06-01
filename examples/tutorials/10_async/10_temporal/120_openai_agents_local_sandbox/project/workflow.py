"""OpenAI Agents SDK + Temporal: Local Sandbox Tutorial

This tutorial demonstrates running an OpenAI Agents SDK ``SandboxAgent`` inside a
Temporal workflow, backed by the **local** (``unix_local``) sandbox. The agent is
a "local sandbox assistant": it answers questions by actually running real shell
commands (e.g. ``python3 --version``, ``ls``, ``python3 -c "..."``) instead of
guessing.

KEY CONCEPTS DEMONSTRATED:
- A ``SandboxAgent`` granted the ``Shell`` capability inside a durable Temporal
  workflow.
- The Temporal sandbox bridge: ``temporal_sandbox_client("local")`` resolves to
  the ``UnixLocalSandboxClient`` registered on the worker via
  ``SandboxClientProvider`` (see ``run_worker.py`` / ``acp.py``). The sandbox tool
  calls run as Temporal activities, so they are durable, retried, and observable.
- Real-time streaming + persistence via ``TemporalStreamingModelProvider`` +
  ``ContextInterceptor`` (configured on the worker) and ``TemporalStreamingHooks``.

IMPORTANT LESSONS (applied below):
  (a) Do NOT post the assistant message yourself with ``adk.messages.create``
      after ``Runner.run``. The ``TemporalStreamingModelProvider`` already streams
      and persists the assistant's response — posting it again would duplicate the
      answer in the UI. We only persist conversation state for the next turn via
      ``result.to_input_list()``.
  (b) Use ``NoopSnapshotSpec()`` so the per-turn workspace snapshot is skipped.
      Without it, stopping the sandbox can raise ``WorkspaceArchiveReadError``.
"""

from __future__ import annotations

import os
import json

from agents import Runner
from temporalio import workflow

from agentex.lib import adk
from agentex.lib.types.acp import SendEventParams, CreateTaskParams
from agentex.lib.types.tracing import SGPTracingProcessorConfig
from agentex.lib.utils.logging import make_logger
from agentex.types.text_content import TextContent
from agentex.lib.utils.model_utils import BaseModel
from agentex.lib.environment_variables import EnvironmentVariables
from agentex.lib.core.temporal.types.workflow import SignalName
from agentex.lib.core.temporal.workflows.workflow import BaseWorkflow
from agentex.lib.core.tracing.tracing_processor_manager import (
    add_tracing_processor_config,
)
from agentex.lib.core.temporal.plugins.openai_agents.hooks.hooks import (
    TemporalStreamingHooks,
)

# OpenAI Agents SDK sandbox imports. These are safe to import at workflow module
# load time; the actual sandbox client is resolved at run time via
# ``temporal_sandbox_client`` (which maps to the worker-registered backend).
with workflow.unsafe.imports_passed_through():
    from agents.sandbox import SandboxAgent, SandboxRunConfig
    from agents.run_config import RunConfig
    from agents.sandbox.snapshot import NoopSnapshotSpec
    from agents.sandbox.capabilities import Shell
    from agents.sandbox.sandboxes.unix_local import UnixLocalSandboxClientOptions
    from temporalio.contrib.openai_agents.workflow import temporal_sandbox_client

# Configure tracing processor (optional - only if you have SGP credentials)
add_tracing_processor_config(
    SGPTracingProcessorConfig(
        sgp_api_key=os.environ.get("SGP_API_KEY", ""),
        sgp_account_id=os.environ.get("SGP_ACCOUNT_ID", ""),
    )
)

environment_variables = EnvironmentVariables.refresh()

if environment_variables.WORKFLOW_NAME is None:
    raise ValueError("Environment variable WORKFLOW_NAME is not set")

if environment_variables.AGENT_NAME is None:
    raise ValueError("Environment variable AGENT_NAME is not set")

logger = make_logger(__name__)

MODEL_NAME = "gpt-4o-mini"
INSTRUCTIONS = """You are a local sandbox assistant.

You have access to shell tools that run real commands on the local machine.

Guidelines:
- ALWAYS use the shell tools to actually run commands — never guess or make up
  output. If the user asks for the Python version, run `python3 --version`. If
  they ask to list files, run `ls`. If they ask you to compute something, use
  `python3 -c "..."`.
- Run the minimal command(s) needed to answer the question.
- Report the real command output back to the user, concisely.
"""


class StateModel(BaseModel):
    """State model for preserving conversation history across turns."""

    input_list: list = []
    turn_number: int = 0


@workflow.defn(name=environment_variables.WORKFLOW_NAME)
class At120OpenaiAgentsLocalSandboxWorkflow(BaseWorkflow):
    """Long-running Temporal workflow that runs a SandboxAgent against the local sandbox."""

    def __init__(self):
        super().__init__(display_name=environment_variables.AGENT_NAME)
        self._complete_task = False
        self._state: StateModel | None = None
        self._task_id = None
        self._trace_id = None
        self._parent_span_id = None

    @workflow.signal(name=SignalName.RECEIVE_EVENT)
    async def on_task_event_send(self, params: SendEventParams) -> None:
        logger.info(f"Received task event: {params.task.id}")

        if self._state is None:
            raise ValueError("State is not initialized")

        self._state.turn_number += 1

        # The ContextInterceptor reads ``self._task_id`` off the workflow
        # instance and threads it through activity headers so the streaming
        # model + hooks know which task to stream/persist to.
        self._task_id = params.task.id
        self._trace_id = params.task.id

        # Add the user message to conversation history.
        self._state.input_list.append({"role": "user", "content": params.event.content.content})

        # Echo back the client's message so it shows up in the UI.
        await adk.messages.create(task_id=params.task.id, content=params.event.content)

        async with adk.tracing.span(
            trace_id=params.task.id,
            name=f"Turn {self._state.turn_number}",
            input=self._state.model_dump(),
        ) as span:
            self._parent_span_id = span.id if span else None

            # Build the sandbox agent. The Shell capability becomes real shell
            # tools backed by the sandbox client resolved at run time.
            agent = SandboxAgent(
                name="Local Sandbox Assistant",
                model=MODEL_NAME,
                instructions=INSTRUCTIONS,
                capabilities=[Shell()],
            )

            # Point the run at the LOCAL sandbox backend registered on the worker
            # under the name "local". ``temporal_sandbox_client`` resolves that
            # registration so the sandbox tool calls execute as Temporal
            # activities (durable + observable).
            #
            # IMPORTANT: ``NoopSnapshotSpec()`` skips the per-turn workspace
            # snapshot — otherwise stopping the sandbox can raise
            # ``WorkspaceArchiveReadError``.
            run_config = RunConfig(
                sandbox=SandboxRunConfig(
                    client=temporal_sandbox_client("local"),
                    options=UnixLocalSandboxClientOptions(),
                    snapshot=NoopSnapshotSpec(),
                )
            )

            # TemporalStreamingHooks creates the lifecycle messages (tool
            # request/response, etc.) and works with the streaming model
            # provider to stream tokens to the UI in real time.
            result = await Runner.run(
                agent,
                self._state.input_list,
                run_config=run_config,
                hooks=TemporalStreamingHooks(task_id=params.task.id),
                max_turns=10,
            )

            # IMPORTANT: We do NOT post the assistant message ourselves here.
            # The TemporalStreamingModelProvider already streamed and persisted
            # the assistant's response. We only persist conversation state for
            # the next turn.
            self._state.input_list = result.to_input_list()

            if span:
                span.output = self._state.model_dump()

    @workflow.run
    async def on_task_create(self, params: CreateTaskParams) -> str:
        logger.info(f"Task created: {params.task.id}")

        self._state = StateModel(input_list=[], turn_number=0)

        await adk.messages.create(
            task_id=params.task.id,
            content=TextContent(
                author="agent",
                content=(
                    f"Task initialized with params:\n{json.dumps(params.params, indent=2)}\n"
                    f"Send me a message and I'll run real shell commands in a local "
                    f"sandbox (backed by Temporal) to answer."
                ),
            ),
        )

        await workflow.wait_condition(lambda: self._complete_task, timeout=None)
        return "Task completed"

    @workflow.signal
    async def complete_task_signal(self) -> None:
        logger.info("Received complete_task signal")
        self._complete_task = True
