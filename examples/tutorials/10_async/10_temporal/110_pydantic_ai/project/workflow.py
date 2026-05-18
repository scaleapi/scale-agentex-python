"""Temporal workflow for the Pydantic AI tutorial.

The workflow holds task state durably across crashes. Its signal handler
delegates the actual agent run to ``temporal_agent.run(...)`` — which
internally schedules model and tool activities, each independently
durable. The ``event_stream_handler`` registered on ``temporal_agent``
pushes streaming deltas to Redis while the model activity runs.
"""

from __future__ import annotations

import json
import os

from temporalio import workflow

from agentex.lib import adk
from agentex.lib.types.acp import SendEventParams, CreateTaskParams
from agentex.lib.types.tracing import SGPTracingProcessorConfig
from agentex.lib.utils.logging import make_logger
from agentex.types.text_content import TextContent
from agentex.lib.environment_variables import EnvironmentVariables
from agentex.lib.core.temporal.types.workflow import SignalName
from agentex.lib.core.temporal.workflows.workflow import BaseWorkflow
from agentex.lib.core.tracing.tracing_processor_manager import (
    add_tracing_processor_config,
)

from project.agent import TaskDeps, temporal_agent

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
class At110PydanticAiWorkflow(BaseWorkflow):
    """Long-running Temporal workflow that delegates each turn to a Pydantic AI TemporalAgent.

    The ``__pydantic_ai_agents__`` attribute is the marker the
    ``PydanticAIPlugin`` looks for at worker startup: it pulls
    ``temporal_agent.temporal_activities`` off this list and registers them
    on the worker automatically — so we don't have to list activities by
    hand in ``run_worker.py``.
    """

    __pydantic_ai_agents__ = [temporal_agent]

    def __init__(self):
        super().__init__(display_name=environment_variables.AGENT_NAME)
        self._complete_task = False
        self._turn_number = 0

    @workflow.signal(name=SignalName.RECEIVE_EVENT)
    async def on_task_event_send(self, params: SendEventParams) -> None:
        """Handle a new user message: echo it, then run the agent durably."""
        logger.info(f"Received task event: {params.task.id}")
        self._turn_number += 1

        # Echo the user's message so it shows up in the UI as a chat bubble.
        await adk.messages.create(task_id=params.task.id, content=params.event.content)

        async with adk.tracing.span(
            trace_id=params.task.id,
            name=f"Turn {self._turn_number}",
            input={"message": params.event.content.content},
        ) as span:
            # temporal_agent.run() is the magic line. From the outside it
            # looks like a regular async call. Internally it schedules:
            #   1. A model activity (LLM HTTP call recorded by Temporal)
            #   2. For each tool the model invokes, a tool activity
            #   3. Each activity is retried, observable, and durable
            # While the model activity runs, the event_stream_handler on
            # temporal_agent pushes deltas to Redis so the UI sees tokens.
            result = await temporal_agent.run(
                params.event.content.content,
                deps=TaskDeps(task_id=params.task.id),
            )
            if span:
                span.output = {"final_output": result.output}

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
                    f"Send me a message and I'll respond using a Pydantic AI agent backed by Temporal."
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
