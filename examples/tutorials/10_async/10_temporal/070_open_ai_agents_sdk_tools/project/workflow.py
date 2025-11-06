"""
OpenAI Agents SDK + Temporal Integration Tutorial

This tutorial demonstrates two key patterns for integrating OpenAI Agents SDK with Temporal workflows:

PATTERN 1: Simple External Tools as Activities (activity_as_tool)
- Convert individual Temporal activities directly into agent tools
- 1:1 mapping between tool calls and activities
- Best for: single non-deterministic operations (API calls, DB queries)
- Example: get_weather activity → weather tool

PATTERN 2: Multiple Activities Within Tools (function_tool with internal activities)
- Create function tools that coordinate multiple activities internally
- 1:many mapping between tool calls and activities
- Best for: complex multi-step operations that need guaranteed sequencing
- Example: move_money tool → withdraw_money + deposit_money activities

Both patterns provide durability, automatic retries, and full observability through Temporal.

WHY THIS APPROACH IS GAME-CHANGING:
===================================
There's a crucial meta-point that should be coming through here: **why is this different?**
This approach is truly transactional because of how the `await` works in Temporal workflows.
Consider a "move money" example - if the operation fails between the withdraw and deposit,
Temporal will resume exactly where it left off - the agent gets real-world flexibility even
if systems die.

**Why even use Temporal? Why are we adding complexity?** The gain is enormous when you
consider what happens without it:

In a traditional approach without Temporal, if you withdraw money but then the system crashes
before depositing, you're stuck in a broken state. The money has been withdrawn, but never
deposited. In a banking scenario, you can't just "withdraw again" - the money is already gone
from the source account, and your agent has no way to recover or know what state it was in.

This is why you can't build very complicated agents without this confidence in transactional
behavior. Temporal gives us:

- **Guaranteed execution**: If the workflow starts, it will complete, even through failures
- **Exact resumption**: Pick up exactly where we left off, not start over
- **Transactional integrity**: Either both operations complete, or the workflow can be designed
  to handle partial completion
- **Production reliability**: Build agents that can handle real-world complexity and failures

Without this foundation, agents remain fragile toys. With Temporal, they become production-ready
systems that can handle the complexities of the real world.
"""

import os
import json
import asyncio
from typing import Any, Dict, List
from datetime import timedelta

from agents import Agent, Runner
from temporalio import workflow
from temporalio.contrib import openai_agents

from agentex.lib import adk
from project.activities import get_weather
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
class At070OpenAiAgentsSdkToolsWorkflow(BaseWorkflow):
    """
    Minimal async workflow template for AgentEx Temporal agents.
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
        logger.info(f"Received task message instruction: {params}")

        if self._state is None:
            raise ValueError("State is not initialized")

        # Increment turn number for tracing
        self._state.turn_number += 1

        self._task_id = params.task.id
        self._trace_id = params.task.id

        # Add the user message to conversation history
        self._state.input_list.append({"role": "user", "content": params.event.content.content})

        # Echo back the client's message to show it in the UI. This is not done by default
        # so the agent developer has full control over what is shown to the user.
        await adk.messages.create(task_id=params.task.id, content=params.event.content)

        # ============================================================================
        # OpenAI Agents SDK + Temporal Integration: Two Patterns for Tool Creation
        # ============================================================================

        # #### When to Use Activities for Tools
        #
        # You'll want to use the activity pattern for tools in the following scenarios:
        #
        # - **API calls within the tool**: Whenever your tool makes an API call (external
        #   service, database, etc.), you must wrap it as an activity since these are
        #   non-deterministic operations that could fail or return different results
        # - **Idempotent single operations**: When the tool performs an already idempotent
        #   single call that you want to ensure gets executed reliably with Temporal's retry
        #   guarantees
        #
        # Let's start with the case where it is non-deterministic. If this is the case, we
        # want this tool to be an activity to guarantee that it will be executed. The way to
        # do this is to add some syntax to make the tool call an activity. Let's create a tool
        # that gives us the weather and create a weather agent. For this example, we will just
        # return a hard-coded string but we can easily imagine this being an API call to a
        # weather service which would make it non-deterministic. First we will create a new
        # file called `activities.py`. Here we will create a function to get the weather and
        # simply add an activity annotation on top.

        # There are TWO key patterns for integrating tools with the OpenAI Agents SDK in Temporal:
        #
        # PATTERN 1: Simple External Tools as Activities
        # PATTERN 2: Multiple Activities Within Tools
        #
        # Choose the right pattern based on your use case:

        # ============================================================================
        # PATTERN 1: Simple External Tools as Activities
        # ============================================================================
        # Use this pattern when:
        # - You have a single non-deterministic operation (API call, DB query, etc.)
        # - You want each tool call to be a single Temporal activity
        # - You want simple 1:1 mapping between tool calls and activities
        #
        # HOW IT WORKS:
        # 1. Define your function as a Temporal activity with @activity.defn (see activities.py)
        # 2. Convert the activity to a tool using activity_as_tool()
        # 3. Each time the agent calls this tool, it creates ONE activity in the workflow
        #
        # BENEFITS:
        # - Automatic retries and durability for each tool call
        # - Clear observability - each tool call shows as an activity in Temporal UI
        # - Temporal handles all the failure recovery automatically

        weather_agent = Agent(
            name="Weather Assistant",
            instructions="You are a helpful weather agent. Use the get_weather tool to get the weather for a given city.",
            tools=[
                # activity_as_tool() converts a Temporal activity into an agent tool
                # The get_weather activity will be executed with durability guarantees
                openai_agents.workflow.activity_as_tool(
                    get_weather,  # This is defined in activities.py as @activity.defn
                    start_to_close_timeout=timedelta(seconds=10),
                ),
            ],
        )

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
        # These hooks create the messages you see in the test output:
        # - Type: tool_request - Agent deciding to call get_weather
        # - Type: tool_response - Result from get_weather activity
        # - Type: text - Final agent response with weather info
        #
        # The hooks work alongside the interceptor/model streaming to provide
        # a complete view of the agent's execution in the UI.
        hooks = TemporalStreamingHooks(task_id=params.task.id)

        # Run the agent - when it calls the weather tool, it will create a get_weather activity
        # Hooks will create messages for tool calls, interceptor enables token streaming
        # Wrap in tracing span to track this turn
        async with adk.tracing.span(
            trace_id=params.task.id,
            name=f"Turn {self._state.turn_number}",
            input=self._state.model_dump(),
        ) as span:
            self._parent_span_id = span.id if span else None
            # Pass the conversation history to Runner.run to maintain context
            result = await Runner.run(weather_agent, self._state.input_list, hooks=hooks)

            # Update the state with the assistant's response for the next turn
            if hasattr(result, "messages") and result.messages:
                for msg in result.messages:
                    # Add new assistant messages to history
                    # Skip messages we already have (user messages we just added)
                    if msg.get("role") == "assistant" and msg not in self._state.input_list:
                        self._state.input_list.append(msg)

            # Set span output for tracing - include full state
            span.output = self._state.model_dump()

        # ============================================================================
        # PATTERN 2: Multiple Activities Within Tools
        # ============================================================================
        # Use this pattern when:
        # - You need multiple sequential non-deterministic operations within one tool
        # - You want to guarantee the sequence of operations (not rely on LLM sequencing)
        # - You need atomic operations that involve multiple steps
        #
        # HOW IT WORKS:
        # 1. Create individual activities for each non-deterministic step (see activities.py)
        # 2. Create a function tool using @function_tool that calls multiple activities internally
        # 3. Each activity call uses workflow.start_activity_method() for durability
        # 4. The tool coordinates the sequence deterministically (not the LLM)
        #
        # BENEFITS:
        # - Guaranteed execution order (withdraw THEN deposit)
        # - Each step is durable and retryable individually
        # - Atomic operations from the agent's perspective
        # - Better than having LLM make multiple separate tool calls

        # UNCOMMENT THIS SECTION TO SEE PATTERN 2 IN ACTION:
        # money_mover_agent = Agent(
        #     name="Money Mover",
        #     instructions="You are a helpful money mover agent. Use the move_money tool to move money from one account to another.",
        #     tools=[
        #         # move_money is defined in tools.py as @function_tool
        #         # Internally, it calls withdraw_money activity THEN deposit_money activity
        #         # This guarantees the sequence and makes both operations durable
        #         move_money,
        #     ],
        # )

        # # Run the agent - when it calls move_money tool, it will create TWO activities:
        # # 1. withdraw_money activity
        # # 2. deposit_money activity (only after withdraw succeeds)
        # result = await Runner.run(money_mover_agent, params.event.content.content)

        # ============================================================================
        # PATTERN COMPARISON SUMMARY:
        # ============================================================================
        #
        # Pattern 1 (activity_as_tool):        | Pattern 2 (function_tool with activities):
        # - Single activity per tool call      | - Multiple activities per tool call
        # - 1:1 tool to activity mapping       | - 1:many tool to activity mapping
        # - Simple non-deterministic ops       | - Complex multi-step operations
        # - Let LLM sequence multiple tools     | - Code controls activity sequencing
        # - Example: get_weather, db_lookup    | - Example: money_transfer, multi_step_workflow
        #
        # BOTH patterns provide:
        # - Automatic retries and failure recovery
        # - Full observability in Temporal UI
        # - Durable execution guarantees
        # - Seamless integration with OpenAI Agents SDK
        # ============================================================================

    @workflow.run
    async def on_task_create(self, params: CreateTaskParams) -> str:
        logger.info(f"Received task create params: {params}")

        # Initialize the conversation state with an empty history
        self._state = StateModel(
            input_list=[],
            turn_number=0,
        )

        # 1. Acknowledge that the task has been created.
        await adk.messages.create(
            task_id=params.task.id,
            content=TextContent(
                author="agent",
                content=f"Hello! I've received your task. Normally you can do some state initialization here, or just pass and do nothing until you get your first event. For now I'm just acknowledging that I've received a task with the following params:\n\n{json.dumps(params.params, indent=2)}.\n\nYou should only see this message once, when the task is created. All subsequent events will be handled by the `on_task_event_send` handler.",
            ),
        )

        await workflow.wait_condition(
            lambda: self._complete_task,
            timeout=None,  # Set a timeout if you want to prevent the task from running indefinitely. Generally this is not needed. Temporal can run hundreds of millions of workflows in parallel and more. Only do this if you have a specific reason to do so.
        )
        return "Task completed"

    @workflow.signal
    async def fulfill_order_signal(self, success: bool) -> None:
        if success == True:
            await self._pending_confirmation.put(True)
