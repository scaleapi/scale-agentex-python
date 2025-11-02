"""
Workflow Activities Tutorial

This tutorial demonstrates using Temporal activities for WORKFLOW ORCHESTRATION
alongside the OpenAI Agents SDK.

KEY PATTERN:
- OpenAI Agents SDK handles LLM interactions (via Runner.run)
- Temporal activities handle everything else (database, notifications, reports)

DIFFERENCE FROM TUTORIAL 020:
- Tutorial 020: Activities AS agent tools (agent decides when to call them)
- Tutorial 040: Activities FOR workflow logic (workflow decides when to call them)

USE CASES:
- Database operations after agent responses
- Progress notifications during long workflows
- Batch processing operations
- Report generation
- External system integration (email, Slack, webhooks)
- Audit logging

WHY THIS MATTERS:
Not everything should go through the agent. Some operations are:
- Part of workflow orchestration (not agent decisions)
- Background operations (notifications, logging)
- Post-processing (saving results, generating reports)
- Infrastructure concerns (health checks, metrics)

These should be workflow-level activities, not agent tools.
"""

import os
from typing import Any, Dict, List
from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy

from agents import Agent, Runner

from agentex.lib import adk
from agentex.lib.types.acp import SendEventParams, CreateTaskParams
from agentex.lib.utils.logging import make_logger
from agentex.lib.utils.model_utils import BaseModel
from agentex.lib.environment_variables import EnvironmentVariables
from agentex.lib.core.temporal.types.workflow import SignalName
from agentex.lib.core.temporal.workflows.workflow import BaseWorkflow
from agentex.lib.core.temporal.plugins.openai_agents.hooks.hooks import TemporalStreamingHooks
from agentex.types.text_content import TextContent

# Import our workflow activities
from project.activities import (
    save_to_database,
    send_notification,
    process_batch,
    generate_report,
)

environment_variables = EnvironmentVariables.refresh()

if not environment_variables.WORKFLOW_NAME:
    raise ValueError("Environment variable WORKFLOW_NAME is not set")

if not environment_variables.AGENT_NAME:
    raise ValueError("Environment variable AGENT_NAME is not set")

if not os.environ.get("OPENAI_API_KEY"):
    raise ValueError(
        "OPENAI_API_KEY environment variable is not set. "
        "Set it in your manifest.yaml or .env file."
    )

logger = make_logger(__name__)


class StateModel(BaseModel):
    """Track workflow state"""
    input_list: List[Dict[str, Any]]
    turn_number: int
    database_saves: int
    notifications_sent: int
    batches_processed: int


@workflow.defn(name=environment_variables.WORKFLOW_NAME)
class WorkflowActivitiesWorkflow(BaseWorkflow):
    """
    Demonstrates using activities for workflow orchestration alongside OpenAI Agents SDK.

    Pattern:
    1. User sends message
    2. Agent processes with LLM (OpenAI Agents SDK)
    3. Workflow saves to database (activity)
    4. Workflow sends notification (activity)
    5. Every 3 messages, process batch (activity)
    """

    def __init__(self):
        super().__init__(display_name=environment_variables.AGENT_NAME)
        self._state: StateModel | None = None
        self._task_id: str | None = None
        self._trace_id: str | None = None
        self._parent_span_id: str | None = None
        self._complete_task = False

    @workflow.signal(name=SignalName.RECEIVE_EVENT)
    async def on_task_event_send(self, params: SendEventParams) -> None:
        if not params.event.content or params.event.content.type != "text":
            return

        # Wait for state to be initialized (handles race condition)
        await workflow.wait_condition(lambda: self._state is not None)

        # Store for streaming
        self._task_id = params.task.id
        self._trace_id = params.task.id
        self._parent_span_id = params.task.id

        # Increment turn
        self._state.turn_number += 1

        # Add user message to history
        user_message = params.event.content.content
        self._state.input_list.append({"role": "user", "content": user_message})

        # Echo to UI
        await adk.messages.create(task_id=params.task.id, content=params.event.content)

        # ============================================================================
        # STEP 1: Agent Processes Message (OpenAI Agents SDK)
        # ============================================================================
        # The agent uses the OpenAI Agents SDK to process the user's message.
        # This automatically becomes a durable Temporal activity via the plugin.

        agent = Agent(
            name="Helpful Assistant",
            instructions="You are a helpful assistant. Provide clear, concise answers.",
        )

        hooks = TemporalStreamingHooks(task_id=params.task.id)

        logger.info(f"[WORKFLOW] Running agent for turn {self._state.turn_number}")
        result = await Runner.run(agent, self._state.input_list, hooks=hooks)

        # Update conversation history and extract response
        agent_response = ""
        if hasattr(result, "messages") and result.messages:
            for msg in result.messages:
                if msg.get("role") == "assistant" and msg not in self._state.input_list:
                    self._state.input_list.append(msg)
                    # Get the last assistant message content
                    if msg.get("role") == "assistant":
                        agent_response = msg.get("content", "")

        # ============================================================================
        # STEP 2: Save to Database (Workflow Activity)
        # ============================================================================
        # After the agent responds, save the interaction to the database.
        # This is a WORKFLOW decision, not an agent decision.

        logger.info(f"[WORKFLOW] Saving conversation to database")

        db_result = await workflow.execute_activity(
            save_to_database,
            args=[params.task.id, {
                "turn": self._state.turn_number,
                "user_message": user_message,
                "agent_response": agent_response
            }],
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=3)
        )

        self._state.database_saves += 1
        logger.info(f"[WORKFLOW] Database save result: {db_result}")

        # ============================================================================
        # STEP 3: Send Notification (Workflow Activity)
        # ============================================================================
        # Send a notification about the interaction.
        # In production: email, Slack, webhook, etc.

        logger.info(f"[WORKFLOW] Sending notification")

        notif_result = await workflow.execute_activity(
            send_notification,
            args=[
                params.task.id,
                f"Turn {self._state.turn_number} completed",
                "email"
            ],
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=3)
        )

        self._state.notifications_sent += 1
        logger.info(f"[WORKFLOW] Notification result: {notif_result}")

        # ============================================================================
        # STEP 4: Batch Processing (Workflow Activity - Conditional)
        # ============================================================================
        # Every 3 messages, process a batch of recent messages.
        # This could be analytics, aggregation, reporting, etc.

        if self._state.turn_number % 3 == 0:
            logger.info(f"[WORKFLOW] Triggering batch processing")

            # Get last 3 messages for batch
            recent_messages = [
                msg.get("content", "")
                for msg in self._state.input_list[-6:]  # Last 3 user+agent pairs
                if isinstance(msg.get("content"), str)
            ]

            batch_result = await workflow.execute_activity(
                process_batch,
                args=[params.task.id, recent_messages, self._state.turn_number // 3],
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=RetryPolicy(maximum_attempts=2)
            )

            self._state.batches_processed += 1
            logger.info(f"[WORKFLOW] Batch result: {batch_result}")

    @workflow.run
    async def on_task_create(self, params: CreateTaskParams) -> None:
        logger.info(f"Workflow started for task: {params.task.id}")

        # Initialize state
        self._state = StateModel(
            input_list=[],
            turn_number=0,
            database_saves=0,
            notifications_sent=0,
            batches_processed=0,
        )

        # Send welcome message
        await adk.messages.create(
            task_id=params.task.id,
            content=TextContent(
                author="agent",
                content=(
                    "👋 Welcome to the Workflow Activities Tutorial!\n\n"
                    "This agent demonstrates using Temporal activities for "
                    "workflow orchestration:\n"
                    "• Agent processes your messages (OpenAI Agents SDK)\n"
                    "• Workflow saves to database (activity)\n"
                    "• Workflow sends notifications (activity)\n"
                    "• Every 3 messages, batch processing runs (activity)\n\n"
                    "Send me a few messages and watch the activities in Temporal UI!"
                ),
            ),
        )

        # Wait for messages indefinitely
        # When the workflow ends (manually or via signal), generate final report
        await workflow.wait_condition(
            lambda: self._complete_task,
            timeout=None
        )

        # ============================================================================
        # FINAL STEP: Generate Report (Workflow Activity)
        # ============================================================================
        # When workflow ends, generate a summary report
        logger.info(f"[WORKFLOW] Generating final report")

        if self._state:
            await workflow.execute_activity(
                generate_report,
                args=[params.task.id, {
                    "total_messages": self._state.turn_number,
                    "database_saves": self._state.database_saves,
                    "notifications_sent": self._state.notifications_sent,
                    "batches_processed": self._state.batches_processed,
                }],
                start_to_close_timeout=timedelta(minutes=2),
                retry_policy=RetryPolicy(maximum_attempts=3)
            )

        logger.info(f"[WORKFLOW] Workflow completed")
