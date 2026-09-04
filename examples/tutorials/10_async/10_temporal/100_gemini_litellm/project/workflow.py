"""
Gemini + LiteLLM + Temporal Integration Tutorial

This tutorial demonstrates how to use Google's Gemini models through LiteLLM
with the OpenAI Agents SDK and Temporal workflows. It shows how to:

1. Use LiteLLM to route requests to Gemini instead of OpenAI
2. Maintain the same durable workflow patterns with a different model provider
3. Leverage the OpenAI Agents SDK interface while using non-OpenAI models

KEY CONCEPTS DEMONSTRATED:
- LiteLLM model provider for multi-model support
- Gemini model integration with OpenAI-compatible interface
- Temporal workflow durability with alternative LLM providers
- Model-agnostic agent patterns

This builds on the OpenAI Agents SDK tutorials, showing how to swap models easily.
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

# Note: GEMINI_API_KEY should be set in your environment
# LiteLLM will use this automatically when routing to Gemini models

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
class At100GeminiLitellmWorkflow(BaseWorkflow):
    """
    Gemini + LiteLLM Temporal Workflow

    This workflow demonstrates using Google's Gemini models through LiteLLM
    with the OpenAI Agents SDK. The key insight is that LiteLLM provides a
    unified interface, allowing you to swap models without changing your
    agent code structure.

    KEY FEATURES:
    - Use Gemini models with OpenAI Agents SDK interface
    - Same durable workflow patterns as OpenAI tutorials
    - Model-agnostic agent development
    - Full observability through Temporal dashboard
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
        Handle incoming user messages and respond using Gemini via LiteLLM

        This signal handler demonstrates using alternative model providers:
        1. Receive user message through Temporal signal
        2. Echo message back to UI for visibility
        3. Create agent with LitellmModel pointing to Gemini
        4. Return agent's response to user

        LITELLM INTEGRATION:
        - LitellmModel wraps the model selection, routing to Gemini
        - The agent interface remains identical to OpenAI examples
        - Temporal durability works the same way regardless of model provider
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
        await adk.messages.create(task_id=params.task.id, content=params.event.content)

        # ============================================================================
        # STEP 2: Wrap execution in tracing span
        # ============================================================================
        async with adk.tracing.span(
            trace_id=params.task.id,
            name=f"Turn {self._state.turn_number}",
            input=self._state.model_dump(),
        ) as span:
            self._parent_span_id = span.id if span else None

            # ============================================================================
            # STEP 3: Create Agent with Gemini via LiteLLM
            # ============================================================================
            # The key difference from OpenAI examples is specifying the model.
            # LiteLLM uses a "provider/model" format:
            # - "gemini/gemini-2.0-flash" for Gemini 2.0 Flash
            # - "gemini/gemini-1.5-pro" for Gemini 1.5 Pro
            # - See https://docs.litellm.ai/docs/providers/gemini for more options
            #
            # You can also use other providers:
            # - "anthropic/claude-3-sonnet-20240229" for Claude
            # - "mistral/mistral-large-latest" for Mistral
            # - And many more!
            #
            # The LitellmProvider configured in acp.py and run_worker.py handles
            # routing the model string to the appropriate provider.

            agent = Agent(
                name="Gemini Assistant",
                instructions="You are a helpful assistant powered by Google's Gemini model. "
                "You respond concisely and clearly to user questions. "
                "When appropriate, mention that you're powered by Gemini via LiteLLM.",
                model="gemini/gemini-2.0-flash",
            )

            # ============================================================================
            # STEP 4: Run Agent with Temporal Durability
            # ============================================================================
            # The Runner.run() call works exactly the same as with OpenAI.
            # LiteLLM handles routing the request to Gemini transparently.
            # Temporal still provides durability and automatic retries.

            result = await Runner.run(agent, self._state.input_list)

            # Update the state with the assistant's response for the next turn
            if hasattr(result, "messages") and result.messages:
                for msg in result.messages:
                    if msg.get("role") == "assistant" and msg not in self._state.input_list:
                        self._state.input_list.append(msg)

            # Set span output for tracing
            span.output = self._state.model_dump()

            # Send the response to the user
            await adk.messages.create(
                task_id=params.task.id,
                content=TextContent(author="agent", content=result.final_output)
            )

    @workflow.run
    async def on_task_create(self, params: CreateTaskParams) -> str:
        """
        Temporal Workflow Entry Point - Long-Running Agent Conversation

        This method runs when the workflow starts and keeps the agent conversation alive.
        The pattern is identical to other tutorials - only the model provider changes.
        """
        logger.info(f"Received task create params: {params}")

        # Initialize the conversation state
        self._state = StateModel(
            input_list=[],
            turn_number=0,
        )

        # Send welcome message
        await adk.messages.create(
            task_id=params.task.id,
            content=TextContent(
                author="agent",
                content=f"Hello! I'm your assistant powered by Google's Gemini model via LiteLLM!\n\n"
                f"This demonstrates how to use alternative model providers with the OpenAI Agents SDK "
                f"and Temporal workflows. The code structure is nearly identical to OpenAI examples - "
                f"only the model specification changes.\n\n"
                f"Task created with params:\n{json.dumps(params.params, indent=2)}\n\n"
                f"Send me a message and I'll respond using Gemini!",
            ),
        )

        # Wait for completion signal
        await workflow.wait_condition(
            lambda: self._complete_task,
            timeout=None,
        )
        return "Agent conversation completed"

    @workflow.signal
    async def complete_task_signal(self) -> None:
        """Signal to gracefully complete the agent conversation workflow"""
        logger.info("Received signal to complete the agent conversation")
        self._complete_task = True
