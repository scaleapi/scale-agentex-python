"""Temporal workflow for the OpenAI Agents harness tutorial.

The workflow stays deterministic: it echoes the user message and delegates the
non-deterministic LLM run to ``run_openai_agent`` (see
``project.activities``). That activity runs the OpenAI Agents SDK and delivers
the turn through the unified harness surface (``OpenAITurn`` +
``UnifiedEmitter.auto_send_turn``).
"""

from __future__ import annotations

import os
import json
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

from agentex.lib import adk
from project.activities import (
    RUN_AGENT_ACTIVITY,
    RunHarnessAgentParams,
    RunHarnessAgentResult,
)
from agentex.lib.types.acp import SendEventParams, CreateTaskParams
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


@workflow.defn(name=environment_variables.WORKFLOW_NAME)
class At140HarnessOpenaiWorkflow(BaseWorkflow):
    """Long-running workflow that runs each turn through the harness activity."""

    def __init__(self):
        super().__init__(display_name=environment_variables.AGENT_NAME)
        self._complete_task = False
        self._turn_number = 0
        # Running conversation (OpenAI Agents SDK input items) so each turn sees
        # the full history, not just the latest user message.
        self._messages: list = []

    @workflow.signal(name=SignalName.RECEIVE_EVENT)
    async def on_task_event_send(self, params: SendEventParams) -> None:
        """Handle a user message: echo it, then run the harness activity durably."""
        logger.info(f"Received task event: {params.task.id}")
        self._turn_number += 1

        # Echo the user's message so it shows up in the UI as a chat bubble.
        await adk.messages.create(task_id=params.task.id, content=params.event.content)

        async with adk.tracing.span(
            trace_id=params.task.id,
            task_id=params.task.id,
            name=f"Turn {self._turn_number}",
            input={"message": params.event.content.content},
        ) as span:
            turn_result = await workflow.execute_activity(
                RUN_AGENT_ACTIVITY,
                RunHarnessAgentParams(
                    task_id=params.task.id,
                    user_message=params.event.content.content,
                    input_list=self._messages,
                    trace_id=params.task.id,
                    parent_span_id=span.id if span else None,
                    # Deterministic timestamp under replay so a retried activity
                    # re-emits this turn's messages with stable ordering.
                    created_at=workflow.now(),
                ),
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=RetryPolicy(maximum_attempts=3),
                result_type=RunHarnessAgentResult,
            )
            # Carry the updated conversation into the next turn.
            self._messages = turn_result.input_list
            if span:
                span.output = {"final_output": turn_result.final_text}

    @workflow.run
    async def on_task_create(self, params: CreateTaskParams) -> str:
        """Workflow entry point — keep the conversation alive for incoming signals."""
        logger.info(f"Task created: {params.task.id}")

        await adk.messages.create(
            task_id=params.task.id,
            content=TextContent(
                author="agent",
                content=(
                    f"Task initialized with params:\n{json.dumps(params.params, indent=2)}\n"
                    f"Send me a message and I'll respond using an OpenAI Agents SDK agent "
                    f"delivered through the unified harness surface."
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
