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

import json
import asyncio

from agents import Agent, Runner
from temporalio import workflow

from agentex.lib import adk
from project.tools import wait_for_confirmation
from agentex.lib.types.acp import SendEventParams, CreateTaskParams
from agentex.lib.utils.logging import make_logger
from agentex.types.text_content import TextContent
from agentex.lib.environment_variables import EnvironmentVariables
from agentex.lib.core.temporal.types.workflow import SignalName
from agentex.lib.core.temporal.workflows.workflow import BaseWorkflow

environment_variables = EnvironmentVariables.refresh()

if environment_variables.WORKFLOW_NAME is None:
    raise ValueError("Environment variable WORKFLOW_NAME is not set")

if environment_variables.AGENT_NAME is None:
    raise ValueError("Environment variable AGENT_NAME is not set")

logger = make_logger(__name__)

@workflow.defn(name=environment_variables.WORKFLOW_NAME)
class ExampleTutorialWorkflow(BaseWorkflow):
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
        self._pending_confirmation: asyncio.Queue[str] = asyncio.Queue()

    @workflow.signal(name=SignalName.RECEIVE_EVENT)
    async def on_task_event_send(self, params: SendEventParams) -> None:
        """
        Handle user messages with human-in-the-loop approval capability.
        
        When the agent needs human approval, it calls wait_for_confirmation which spawns
        a child workflow that waits for external signals before continuing.
        """
        logger.info(f"Received task message instruction: {params}")
            
        # Echo user message back to UI
        await adk.messages.create(task_id=params.task.id, content=params.event.content)

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
        result = await Runner.run(confirm_order_agent, params.event.content.content)

        # Send response back to user (includes result of any human approval process)
        await adk.messages.create(
            task_id=params.task.id,
            content=TextContent(
                author="agent",
                content=result.final_output,
            ),
        )

    @workflow.run
    async def on_task_create(self, params: CreateTaskParams) -> str:
        """
        Workflow entry point - starts the long-running human-in-the-loop agent.
        
        Handles both automated decisions and human approval workflows durably.
        To approve waiting actions: temporal workflow signal --workflow-id="child-workflow-id" --name="fulfill_order_signal" --input=true
        """
        logger.info(f"Received task create params: {params}")

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
