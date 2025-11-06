"""
OpenAI Agents SDK + Temporal Integration: Hello World Tutorial

This tutorial demonstrates the fundamental integration between OpenAI Agents SDK and Temporal workflows.
It shows how to:

1. Set up a basic Temporal workflow with OpenAI Agents SDK
2. Create a simple agent that responds to user messages
3. See how agent conversations become durable through Temporal
4. Understand the automatic activity creation for model invocations

KEY CONCEPTS DEMONSTRATED:
- Basic agent creation with OpenAI Agents SDK
- Temporal workflow durability for agent conversations
- Automatic activity creation for LLM calls (visible in Temporal UI)
- Long-running agent workflows that can survive restarts

This is the foundation before moving to more advanced patterns with tools and activities.
"""

import os
import json
from typing import Any, Dict, List

from agents import Agent, Runner
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
class At060OpenAiAgentsSdkHelloWorldWorkflow(BaseWorkflow):
    """
    Hello World Temporal Workflow with OpenAI Agents SDK Integration

    This workflow demonstrates the basic pattern for integrating OpenAI Agents SDK
    with Temporal workflows. It shows how agent conversations become durable and
    observable through Temporal's workflow engine.

    KEY FEATURES:
    - Durable agent conversations that survive process restarts
    - Automatic activity creation for LLM calls (visible in Temporal UI)
    - Long-running workflows that can handle multiple user interactions
    - Full observability and monitoring through Temporal dashboard
    """

    def __init__(self):
        super().__init__(display_name=environment_variables.AGENT_NAME)
        self._complete_task = False
        self._state: StateModel | None = None
        self._task_id = None
        self._trace_id = None
        self._parent_span_id = None

    @workflow.signal(name=SignalName.RECEIVE_EVENT)
    async def on_task_event_send(self, params: SendEventParams) -> None:
        """
        Handle incoming user messages and respond using OpenAI Agents SDK

        This signal handler demonstrates the basic integration pattern:
        1. Receive user message through Temporal signal
        2. Echo message back to UI for visibility
        3. Create and run OpenAI agent (automatically becomes a Temporal activity)
        4. Return agent's response to user

        TEMPORAL INTEGRATION MAGIC:
        - When Runner.run() executes, it automatically creates a "invoke_model_activity"
        - This activity is visible in Temporal UI with full observability
        - If the LLM call fails, Temporal automatically retries it
        - The entire conversation is durable and survives process restarts
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

        # ============================================================================
        # STEP 1: Echo User Message
        # ============================================================================
        # Echo back the client's message to show it in the UI. This is not done by default
        # so the agent developer has full control over what is shown to the user.
        await adk.messages.create(task_id=params.task.id, content=params.event.content)

        # ============================================================================
        # STEP 2: Wrap execution in tracing span
        # ============================================================================
        # Create a span to track this turn of the conversation
        async with adk.tracing.span(
            trace_id=params.task.id,
            name=f"Turn {self._state.turn_number}",
            input=self._state.model_dump(),
        ) as span:
            self._parent_span_id = span.id if span else None

            # ============================================================================
            # STEP 3: Create OpenAI Agent
            # ============================================================================
            # Create a simple agent using OpenAI Agents SDK. This agent will respond in haikus
            # to demonstrate the basic functionality. No tools needed for this hello world example.
            #
            # IMPORTANT: The OpenAI Agents SDK plugin (configured in acp.py and run_worker.py)
            # automatically converts agent interactions into Temporal activities for durability.

            agent = Agent(
                name="Haiku Assistant",
                instructions="You are a friendly assistant who always responds in the form of a haiku. "
                "Each response should be exactly 3 lines following the 5-7-5 syllable pattern.",
            )

            # ============================================================================
            # STEP 4: Run Agent with Temporal Durability + Streaming + Conversation History
            # ============================================================================
            # This is where the magic happens! When Runner.run() executes:
            # 1. The OpenAI Agents SDK makes LLM calls to generate responses
            # 2. The plugin automatically wraps these calls as Temporal activities
            # 3. You'll see "invoke_model_activity" appear in the Temporal UI
            # 4. If the LLM call fails, Temporal retries it automatically
            # 5. The conversation state is preserved even if the worker restarts
            #
            # STREAMING MAGIC (via Interceptors + Model Provider):
            # - The ContextInterceptor threads task_id through activity headers
            # - The TemporalStreamingModelProvider returns a model that streams to Redis
            # - The model streams tokens in real-time while maintaining determinism
            # - Complete response is still returned to Temporal for replay safety
            #
            # CONVERSATION HISTORY:
            # - We pass self._state.input_list which contains the full conversation history
            # - This allows the agent to maintain context across multiple turns
            # - The agent can reference previous messages and build on the discussion

            # IMPORTANT NOTE ABOUT AGENT RUN CALLS:
            # =====================================
            # Notice that we don't need to wrap the Runner.run() call in an activity!
            # This might feel weird for anyone who has used Temporal before, as typically
            # non-deterministic operations like LLM calls would need to be wrapped in activities.
            # However, the OpenAI Agents SDK plugin is handling all of this automatically
            # behind the scenes.
            #
            # Another benefit of this approach is that we don't have to serialize the arguments,
            # which would typically be the case with Temporal activities - the plugin handles
            # all of this for us, making the developer experience much smoother.

            # Pass the conversation history to Runner.run to maintain context
            # The input_list contains all previous messages in OpenAI format
            result = await Runner.run(agent, self._state.input_list)

            # Update the state with the assistant's response for the next turn
            # The result contains the full updated conversation including the assistant's response
            if hasattr(result, "messages") and result.messages:
                # Extract the assistant message from the result
                # OpenAI Agents SDK returns the full conversation including the new assistant message
                for msg in result.messages:
                    # Add new assistant messages to history
                    # Skip messages we already have (user messages we just added)
                    if msg.get("role") == "assistant" and msg not in self._state.input_list:
                        self._state.input_list.append(msg)

            # Set span output for tracing - include full state
            span.output = self._state.model_dump()

        # ============================================================================
        # WHAT YOU'LL SEE IN TEMPORAL UI:
        # ============================================================================
        # After running this:
        # 1. Go to localhost:8080 (Temporal UI)
        # 2. Find your workflow execution
        # 3. You'll see an "invoke_model_activity" that shows:
        #    - Execution time for the LLM call
        #    - Input parameters (user message)
        #    - Output (agent's haiku response)
        #    - Retry attempts (if any failures occurred)
        #
        # This gives you full observability into your agent's LLM interactions!
        # ============================================================================

    @workflow.run
    async def on_task_create(self, params: CreateTaskParams) -> str:
        """
        Temporal Workflow Entry Point - Long-Running Agent Conversation

        This method runs when the workflow starts and keeps the agent conversation alive.
        It demonstrates Temporal's ability to run workflows for extended periods (minutes,
        hours, days, or even years) while maintaining full durability.

        TEMPORAL WORKFLOW LIFECYCLE:
        1. Workflow starts when a task is created
        2. Sends initial acknowledgment message to user
        3. Waits indefinitely for user messages (handled by on_task_event_send signal)
        4. Each user message triggers the signal handler which runs the OpenAI agent
        5. Workflow continues running until explicitly completed or canceled

        DURABILITY BENEFITS:
        - Workflow survives worker restarts, deployments, infrastructure failures
        - All agent conversation history is preserved in Temporal's event store
        - Can resume from exact point of failure without losing context
        - Scales to handle millions of concurrent agent conversations
        """
        logger.info(f"Received task create params: {params}")

        # ============================================================================
        # WORKFLOW INITIALIZATION: Initialize State
        # ============================================================================
        # Initialize the conversation state with an empty history
        # This will be populated as the conversation progresses
        self._state = StateModel(
            input_list=[],
            turn_number=0,
        )

        # ============================================================================
        # WORKFLOW INITIALIZATION: Send Welcome Message
        # ============================================================================
        # Acknowledge that the task has been created and the agent is ready.
        # This message appears once when the conversation starts.
        await adk.messages.create(
            task_id=params.task.id,
            content=TextContent(
                author="agent",
                content=f"🌸 Hello! I'm your Haiku Assistant, powered by OpenAI Agents SDK + Temporal! 🌸\n\n"
                f"I'll respond to all your messages in beautiful haiku form. "
                f"This conversation is now durable - even if I restart, our chat continues!\n\n"
                f"Task created with params:\n{json.dumps(params.params, indent=2)}\n\n"
                f"Send me a message and I'll respond with a haiku! 🎋",
            ),
        )

        # ============================================================================
        # WORKFLOW PERSISTENCE: Wait for Completion Signal
        # ============================================================================
        # This is the key to Temporal's power: the workflow runs indefinitely,
        # handling user messages through signals (on_task_event_send) until
        # explicitly told to complete.
        #
        # IMPORTANT: This wait_condition keeps the workflow alive and durable:
        # - No timeout = workflow can run forever (perfect for ongoing conversations)
        # - Temporal can handle millions of such concurrent workflows
        # - If worker crashes, workflow resumes exactly where it left off
        # - All conversation state is preserved in Temporal's event log
        await workflow.wait_condition(
            lambda: self._complete_task,
            timeout=None,  # No timeout = truly long-running agent conversation
        )
        return "Agent conversation completed"

    @workflow.signal
    async def complete_task_signal(self) -> None:
        """
        Signal to gracefully complete the agent conversation workflow

        This signal can be sent to end the workflow cleanly. In a real application,
        you might trigger this when a user ends the conversation or after a period
        of inactivity.
        """
        logger.info("Received signal to complete the agent conversation")
        self._complete_task = True
