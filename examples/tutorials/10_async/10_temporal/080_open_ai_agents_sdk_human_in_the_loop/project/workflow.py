"""
OpenAI Agents SDK + Temporal Integration: Human-in-the-Loop Tutorial

This tutorial demonstrates how to pause agent execution and wait for human approval
using Temporal's child workflows and signals.

KEY CONCEPTS:
- Child workflows: Independent workflows spawned by parent for human interaction
- Signals: External systems can send messages to running workflows
- Durable waiting: Agents can wait indefinitely for human input without losing state

WHY THIS MATTERS:
Without Temporal, if your system crashes while waiting for human approval, you lose
all context. With Temporal, the agent resumes exactly where it left off after
system failures, making human-in-the-loop workflows production-ready.

PATTERN:
1. Agent calls wait_for_confirmation tool
2. Tool spawns child workflow that waits for signal
3. Human approves via CLI/web app
4. Child workflow completes, agent continues

Usage: `temporal workflow signal --workflow-id="child-workflow-id" --name="fulfill_order_signal" --input=true`
"""

import os
import json
import asyncio
from typing import Any, Dict, List

from agents import Agent, Runner
from temporalio import workflow

from agentex.lib import adk
from project.tools import wait_for_confirmation
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
from agentex.lib.core.temporal.plugins.openai_agents.hooks.hooks import TemporalStreamingHooks

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

# Validate OpenAI API key is set
if not os.environ.get("OPENAI_API_KEY"):
    raise ValueError(
        "OPENAI_API_KEY environment variable is not set. "
        "This tutorial requires an OpenAI API key to run the OpenAI Agents SDK. "
        "Please set OPENAI_API_KEY in your environment or manifest.yaml file."
    )

logger = make_logger(__name__)


class StateModel(BaseModel):
    """
    State model for preserving conversation history across turns.

    This allows the agent to maintain context throughout the conversation,
    making it possible to reference previous messages and build on the discussion.
    """

    input_list: List[Dict[str, Any]]
    turn_number: int


@workflow.defn(name=environment_variables.WORKFLOW_NAME)
class At080OpenAiAgentsSdkHumanInTheLoopWorkflow(BaseWorkflow):
    """
    Human-in-the-Loop Temporal Workflow

    Demonstrates agents that can pause execution and wait for human approval.
    When approval is needed, the agent spawns a child workflow that waits for
    external signals (human input) before continuing.

    Benefits: Durable waiting, survives system failures, scalable to millions of workflows.
    """

    def __init__(self):
        super().__init__(display_name=environment_variables.AGENT_NAME)
        self._complete_task = False
        self._state: StateModel | None = None
        self._pending_confirmation: asyncio.Queue[str] = asyncio.Queue()
        self._task_id = None
        self._trace_id = None
        self._parent_span_id = None

    @workflow.signal(name=SignalName.RECEIVE_EVENT)
    async def on_task_event_send(self, params: SendEventParams) -> None:
        """
        Handle user messages with human-in-the-loop approval capability.

        When the agent needs human approval, it calls wait_for_confirmation which spawns
        a child workflow that waits for external signals before continuing.
        """
        logger.info(f"Received task message instruction: {params}")

        if self._state is None:
            raise ValueError("State is not initialized")

        # Increment turn number for tracing
        self._state.turn_number += 1

        self._task_id = params.task.id
        self._trace_id = params.task.id

        # Add the user message to conversation history
        self._state.input_list.append({"role": "user", "content": params.event.content.content})

        # Echo user message back to UI
        await adk.messages.create(task_id=params.task.id, content=params.event.content)

        # ============================================================================
        # STREAMING SETUP: Store task_id for the Interceptor
        # ============================================================================
        # These instance variables are read by ContextWorkflowOutboundInterceptor
        # which injects them into activity headers. This enables streaming without
        # forking the Temporal plugin!
        #
        # How streaming works (Interceptor + Model Provider + Hooks):
        # 1. We store task_id in workflow instance variable (here)
        # 2. ContextWorkflowOutboundInterceptor reads it via workflow.instance()
        # 3. Interceptor injects task_id into activity headers
        # 4. ContextActivityInboundInterceptor extracts from headers
        # 5. Sets streaming_task_id ContextVar inside the activity
        # 6. TemporalStreamingModel reads from ContextVar and streams to Redis
        # 7. TemporalStreamingHooks creates placeholder messages for tool calls
        #
        # This approach uses STANDARD Temporal components - no forked plugin needed!
        self._task_id = params.task.id
        self._trace_id = params.task.id
        self._parent_span_id = params.task.id

        # ============================================================================
        # HOOKS: Create Streaming Lifecycle Messages
        # ============================================================================
        # TemporalStreamingHooks integrates with OpenAI Agents SDK lifecycle events
        # to create messages in the database for tool calls, reasoning, etc.
        #
        # What hooks do:
        # - on_tool_call_start(): Creates tool_request message with arguments
        # - on_tool_call_done(): Creates tool_response message with result
        # - on_model_stream_part(): Called for each streaming chunk (handled by TemporalStreamingModel)
        # - on_run_done(): Marks the final response as complete
        #
        # For human-in-the-loop workflows, hooks create messages showing:
        # - Type: tool_request - Agent deciding to call wait_for_confirmation
        # - Type: tool_response - Result after human approval (child workflow completion)
        # - Type: text - Final agent response after approval received
        #
        # The hooks work alongside the interceptor/model streaming to provide
        # a complete view of the agent's execution in the UI.
        hooks = TemporalStreamingHooks(task_id=params.task.id)

        # Create agent with human-in-the-loop capability
        # The wait_for_confirmation tool spawns a child workflow that waits for external signals
        confirm_order_agent = Agent(
            name="Confirm Order",
            instructions="You are a helpful confirm order agent. When a user asks you to confirm an order, use the wait_for_confirmation tool to wait for confirmation.",
            tools=[
                wait_for_confirmation,
            ],
        )

        # Run agent - when human approval is needed, it will spawn child workflow and wait
        # Hooks will create messages for tool calls, interceptor enables token streaming
        # Wrap in tracing span to track this turn
        async with adk.tracing.span(
            trace_id=params.task.id,
            name=f"Turn {self._state.turn_number}",
            input=self._state.model_dump(),
        ) as span:
            self._parent_span_id = span.id if span else None
            # Pass the conversation history to Runner.run to maintain context
            result = await Runner.run(confirm_order_agent, self._state.input_list, hooks=hooks)

            # Update the state with the assistant's response for the next turn
            if hasattr(result, "messages") and result.messages:
                for msg in result.messages:
                    # Add new assistant messages to history
                    # Skip messages we already have (user messages we just added)
                    if msg.get("role") == "assistant" and msg not in self._state.input_list:
                        self._state.input_list.append(msg)

            # Set span output for tracing - include full state
            span.output = self._state.model_dump()

    @workflow.run
    async def on_task_create(self, params: CreateTaskParams) -> str:
        """
        Workflow entry point - starts the long-running human-in-the-loop agent.

        Handles both automated decisions and human approval workflows durably.
        To approve waiting actions: temporal workflow signal --workflow-id="child-workflow-id" --name="fulfill_order_signal" --input=true
        """
        logger.info(f"Received task create params: {params}")

        # Initialize the conversation state with an empty history
        self._state = StateModel(
            input_list=[],
            turn_number=0,
        )

        # Send welcome message when task is created
        await adk.messages.create(
            task_id=params.task.id,
            content=TextContent(
                author="agent",
                content=f"Hello! I've received your task. Normally you can do some state initialization here, or just pass and do nothing until you get your first event. For now I'm just acknowledging that I've received a task with the following params:\n\n{json.dumps(params.params, indent=2)}.\n\nYou should only see this message once, when the task is created. All subsequent events will be handled by the `on_task_event_send` handler.",
            ),
        )

        # Keep workflow running indefinitely to handle user messages and human approvals
        # This survives system failures and can resume exactly where it left off
        await workflow.wait_condition(
            lambda: self._complete_task,
            timeout=None,  # No timeout for long-running human-in-the-loop workflows
        )
        return "Task completed"

    # TEMPORAL UI (localhost:8080):
    # - Main workflow shows agent activities + ChildWorkflow activity when approval needed
    # - Child workflow appears as separate "child-workflow-id" that waits for signal
    # - Timeline: invoke_model_activity → ChildWorkflow (waiting) → invoke_model_activity (after approval)
    #
    # To approve: temporal workflow signal --workflow-id="child-workflow-id" --name="fulfill_order_signal" --input=true
    # Production: Replace CLI with web dashboards/APIs that send signals programmatically
