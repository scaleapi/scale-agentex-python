# ruff: noqa: ARG001
from __future__ import annotations

import os
import json
from typing import Any, Dict, List, override

from mcp import StdioServerParameters
from dotenv import load_dotenv

# Simple guardrail output model for this example
from pydantic import BaseModel
from temporalio import workflow
from openai.types.shared import Reasoning

from agentex.lib import adk
from agentex.lib.types.acp import SendEventParams, CreateTaskParams
from agentex.lib.adk.models import ModelSettings
from agentex.lib.types.tracing import SGPTracingProcessorConfig
from agentex.lib.utils.logging import make_logger
from agentex.types.text_content import TextContent
from agentex.lib.utils.model_utils import BaseModel
from agentex.lib.core.base.run_context import RunContextWrapper
from agentex.lib.environment_variables import EnvironmentVariables
from agentex.lib.core.temporal.types.workflow import SignalName
from agentex.lib.core.temporal.workflows.workflow import BaseWorkflow
from agentex.lib.core.tracing.tracing_processor_manager import (
    add_tracing_processor_config,
)
from agentex.lib.core.temporal.activities.adk.providers.openai_activities import (  # noqa: E501
    FunctionTool,
    TemporalInputGuardrail,
    TemporalOutputGuardrail,
)


class GuardrailFunctionOutput(BaseModel):
    """Output from a guardrail function."""
    output_info: Dict[str, Any]
    tripwire_triggered: bool


# Type alias for the agent parameter in guardrail functions
Agent = Any

environment_variables = EnvironmentVariables.refresh()
load_dotenv(dotenv_path=".env")

add_tracing_processor_config(
    SGPTracingProcessorConfig(
        sgp_api_key=os.environ.get("SCALE_GP_API_KEY", ""),
        sgp_account_id=os.environ.get("SCALE_GP_ACCOUNT_ID", ""),
    )
)

if not environment_variables.WORKFLOW_NAME:
    raise ValueError("Environment variable WORKFLOW_NAME is not set")

if not environment_variables.AGENT_NAME:
    raise ValueError("Environment variable AGENT_NAME is not set")

logger = make_logger(__name__)


class StateModel(BaseModel):
    input_list: List[Dict[str, Any]]
    turn_number: int


MCP_SERVERS = [
    StdioServerParameters(
        command="npx",
        args=["-y", "@modelcontextprotocol/server-sequential-thinking"],
    ),
    StdioServerParameters(
        command="uvx",
        args=["openai-websearch-mcp"],
        env={"OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY", "")},
    ),
]


async def calculator(context: RunContextWrapper, args: str) -> str:  # noqa: ARG001
    """
    Simple calculator that can perform basic arithmetic operations.

    Args:
        context: The run context wrapper
        args: JSON string containing the operation and operands

    Returns:
        String representation of the calculation result
    """
    try:
        # Parse the JSON arguments
        parsed_args = json.loads(args)
        operation = parsed_args.get("operation")
        a = parsed_args.get("a")
        b = parsed_args.get("b")

        if operation is None or a is None or b is None:
            return (
                "Error: Missing required parameters. "
                "Please provide 'operation', 'a', and 'b'."
            )

        # Convert to numbers
        try:
            a = float(a)
            b = float(b)
        except (ValueError, TypeError):
            return "Error: 'a' and 'b' must be valid numbers."

        # Perform the calculation
        if operation == "add":
            result = a + b
        elif operation == "subtract":
            result = a - b
        elif operation == "multiply":
            result = a * b
        elif operation == "divide":
            if b == 0:
                return "Error: Division by zero is not allowed."
            result = a / b
        else:
            supported_ops = "add, subtract, multiply, divide"
            return (
                f"Error: Unknown operation '{operation}'. "
                f"Supported operations: {supported_ops}."
            )

        # Format the result nicely
        if result == int(result):
            return f"The result of {a} {operation} {b} is {int(result)}"
        else:
            formatted = f"{result:.6f}".rstrip("0").rstrip(".")
            return f"The result of {a} {operation} {b} is {formatted}"

    except json.JSONDecodeError:
        return "Error: Invalid JSON format in arguments."
    except Exception as e:
        return f"Error: An unexpected error occurred: {str(e)}"


"""
Guardrails for Testing:
- Input Guardrails:
  - Spaghetti: Blocks any mention of "spaghetti" in user messages
  - Soup: Blocks any mention of "soup" in user messages
- Output Guardrails:
  - Pizza: Blocks the AI from mentioning "pizza" in responses
  - Sushi: Blocks the AI from mentioning "sushi" in responses

To test:
- Input: "Tell me about spaghetti" or "What's your favorite soup?"
- Output: Ask "What are popular Italian foods?" (might trigger pizza guardrail)
         or "What are popular Japanese foods?" (might trigger sushi guardrail)
"""


# Define the spaghetti guardrail function
async def check_spaghetti_guardrail(
    ctx: RunContextWrapper[None],
    agent: Agent,
    input: str | list
) -> GuardrailFunctionOutput:
    """
    A simple guardrail that checks if 'spaghetti' is mentioned in the input.
    """
    # Convert input to string to check
    input_text = ""
    if isinstance(input, str):
        input_text = input.lower()
    elif isinstance(input, list):
        # For list of messages, check all user messages
        for msg in input:
            if isinstance(msg, dict) and msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, str):
                    input_text += " " + content.lower()

    # Check if spaghetti is mentioned
    contains_spaghetti = "spaghetti" in input_text

    return GuardrailFunctionOutput(
        output_info={
            "contains_spaghetti": contains_spaghetti,
            "checked_text": (
                input_text[:200] + "..."
                if len(input_text) > 200 else input_text
            ),
            "rejection_message": (
                "I'm sorry, but I cannot process messages about spaghetti. "
                "This guardrail was put in place for demonstration purposes. "
                "Please ask me about something else!"
            ) if contains_spaghetti else None
        },
        tripwire_triggered=contains_spaghetti
    )


# Define soup input guardrail function
async def check_soup_guardrail(
    ctx: RunContextWrapper[None],
    agent: Agent,
    input: str | list
) -> GuardrailFunctionOutput:
    """
    A guardrail that checks if 'soup' is mentioned in the input.
    """
    # Convert input to string to check
    input_text = ""
    if isinstance(input, str):
        input_text = input.lower()
    elif isinstance(input, list):
        # For list of messages, check all user messages
        for msg in input:
            if isinstance(msg, dict) and msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, str):
                    input_text += " " + content.lower()

    # Check if soup is mentioned
    contains_soup = "soup" in input_text

    return GuardrailFunctionOutput(
        output_info={
            "contains_soup": contains_soup,
            "checked_text": (
                input_text[:200] + "..."
                if len(input_text) > 200 else input_text
            ),
            "rejection_message": (
                "I'm sorry, but I cannot process messages about soup. "
                "This is a demonstration guardrail for testing purposes. "
                "Please ask about something other than soup!"
            ) if contains_soup else None
        },
        tripwire_triggered=contains_soup
    )


# Create the input guardrails
SPAGHETTI_GUARDRAIL = TemporalInputGuardrail(
    guardrail_function=check_spaghetti_guardrail,
    name="spaghetti_guardrail"
)

SOUP_GUARDRAIL = TemporalInputGuardrail(
    guardrail_function=check_soup_guardrail,
    name="soup_guardrail"
)


# Define pizza output guardrail function
async def check_pizza_guardrail(
    ctx: RunContextWrapper[None],
    agent: Agent,
    output: str
) -> GuardrailFunctionOutput:
    """
    An output guardrail that prevents mentioning pizza.
    """
    output_text = output.lower() if isinstance(output, str) else ""
    contains_pizza = "pizza" in output_text
    
    return GuardrailFunctionOutput(
        output_info={
            "contains_pizza": contains_pizza,
            "rejection_message": (
                "I cannot provide this response as it mentions pizza. "
                "Due to content policies, I need to avoid discussing pizza. "
                "Let me provide a different response."
            ) if contains_pizza else None
        },
        tripwire_triggered=contains_pizza
    )


# Define sushi output guardrail function
async def check_sushi_guardrail(
    ctx: RunContextWrapper[None],
    agent: Agent,
    output: str
) -> GuardrailFunctionOutput:
    """
    An output guardrail that prevents mentioning sushi.
    """
    output_text = output.lower() if isinstance(output, str) else ""
    contains_sushi = "sushi" in output_text
    
    return GuardrailFunctionOutput(
        output_info={
            "contains_sushi": contains_sushi,
            "rejection_message": (
                "I cannot mention sushi in my response. "
                "This guardrail prevents discussions about sushi for demonstration purposes. "
                "Please let me provide information about other topics."
            ) if contains_sushi else None
        },
        tripwire_triggered=contains_sushi
    )


# Create the output guardrails
PIZZA_GUARDRAIL = TemporalOutputGuardrail(
    guardrail_function=check_pizza_guardrail,
    name="pizza_guardrail"
)

SUSHI_GUARDRAIL = TemporalOutputGuardrail(
    guardrail_function=check_sushi_guardrail,
    name="sushi_guardrail"
)


# Example output guardrail function (kept for reference)
async def check_output_length_guardrail(
    ctx: RunContextWrapper[None],
    agent: Agent,
    output: str
) -> GuardrailFunctionOutput:
    """
    A simple output guardrail that checks if the response is too long.
    """
    # Check the length of the output
    max_length = 1000  # Maximum allowed characters
    is_too_long = len(output) > max_length if isinstance(output, str) else False
    
    return GuardrailFunctionOutput(
        output_info={
            "output_length": len(output) if isinstance(output, str) else 0,
            "max_length": max_length,
            "is_too_long": is_too_long,
            "rejection_message": (
                f"I'm sorry, but my response is too long ({len(output)} characters). "
                f"Please ask a more specific question so I can provide a concise answer "
                f"(max {max_length} characters)."
            ) if is_too_long else None
        },
        tripwire_triggered=is_too_long
    )


# Uncomment to use the output guardrail
# from agentex.lib.core.temporal.activities.adk.providers.openai_activities import TemporalOutputGuardrail
# OUTPUT_LENGTH_GUARDRAIL = TemporalOutputGuardrail(
#     guardrail_function=check_output_length_guardrail,
#     name="output_length_guardrail"
# )


# Create the calculator tool
CALCULATOR_TOOL = FunctionTool(
    name="calculator",
    description=(
        "Performs basic arithmetic operations (add, subtract, multiply, "
        "divide) on two numbers."
    ),
    params_json_schema={
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": ["add", "subtract", "multiply", "divide"],
                "description": "The arithmetic operation to perform",
            },
            "a": {"type": "number", "description": "The first number"},
            "b": {"type": "number", "description": "The second number"},
        },
        "required": ["operation", "a", "b"],
        "additionalProperties": False,
    },
    strict_json_schema=True,
    on_invoke_tool=calculator,
)


@workflow.defn(name=environment_variables.WORKFLOW_NAME)
class At050AgentChatGuardrailsWorkflow(BaseWorkflow):
    """
    Minimal async workflow template for AgentEx Temporal agents.
    """

    def __init__(self):
        super().__init__(display_name=environment_variables.AGENT_NAME)
        self._complete_task = False
        self._state: StateModel | None = None

    @workflow.signal(name=SignalName.RECEIVE_EVENT)
    @override
    async def on_task_event_send(self, params: SendEventParams) -> None:

        if not params.event.content:
            return
        if params.event.content.type != "text":
            raise ValueError(f"Expected text message, got {params.event.content.type}")

        if params.event.content.author != "user":
            raise ValueError(
                f"Expected user message, got {params.event.content.author}"
            )

        if self._state is None:
            raise ValueError("State is not initialized")

        # Increment the turn number
        self._state.turn_number += 1
        # Add the new user message to the message history
        self._state.input_list.append(
            {"role": "user", "content": params.event.content.content}
        )

        async with adk.tracing.span(
            trace_id=params.task.id,
            name=f"Turn {self._state.turn_number}",
            input=self._state,
        ) as span:
            # Echo back the user's message so it shows up in the UI.
            # This is not done by default so the agent developer has full
            # control over what is shown to the user.
            await adk.messages.create(
                task_id=params.task.id,
                trace_id=params.task.id,
                content=params.event.content,
                parent_span_id=span.id if span else None,
            )

            if not os.environ.get("OPENAI_API_KEY"):
                await adk.messages.create(
                    task_id=params.task.id,
                    trace_id=params.task.id,
                    content=TextContent(
                        author="agent",
                        content=(
                            "Hey, sorry I'm unable to respond to your message "
                            "because you're running this example without an "
                            "OpenAI API key. Please set the OPENAI_API_KEY "
                            "environment variable to run this example. Do this "
                            "by either by adding a .env file to the project/ "
                            "directory or by setting the environment variable "
                            "in your terminal."
                        ),
                    ),
                    parent_span_id=span.id if span else None,
                )

            # Call an LLM to respond to the user's message
            # When send_as_agent_task_message=True, returns a TaskMessage
            result = await adk.providers.openai.run_agent_streamed_auto_send(
                task_id=params.task.id,
                trace_id=params.task.id,
                input_list=self._state.input_list,
                mcp_server_params=MCP_SERVERS,
                agent_name="Tool-Enabled Assistant",
                agent_instructions=(
                    "You are a helpful assistant that can answer "
                    "questions using various tools. You have access to "
                    "sequential thinking and web search capabilities "
                    "through MCP servers, as well as a calculator tool "
                    "for performing basic arithmetic operations. Use "
                    "these tools when appropriate to provide accurate "
                    "and well-reasoned responses."
                ),
                parent_span_id=span.id if span else None,
                model="gpt-5-mini",
                model_settings=ModelSettings(
                    # Include reasoning items in the response
                    # (IDs, summaries)
                    # response_include=["reasoning.encrypted_content"],
                    # Ask the model to include a short reasoning summary
                    reasoning=Reasoning(effort="medium", summary="detailed"),
                ),
                tools=[CALCULATOR_TOOL],
                input_guardrails=[SPAGHETTI_GUARDRAIL, SOUP_GUARDRAIL],
                output_guardrails=[PIZZA_GUARDRAIL, SUSHI_GUARDRAIL],
            )
            
            # Update state with the final input list from result
            if self._state and result:
                final_list = getattr(result, "final_input_list", None)
                if final_list is not None:
                    self._state.input_list = final_list

            # Set the span output to the state for the next turn
            if span and self._state:
                span.output = self._state.model_dump()

    @workflow.run
    @override
    async def on_task_create(self, params: CreateTaskParams) -> None:
        logger.info(f"Received task create params: {params}")

        # 1. Initialize the state. You can either do this here or in the
        # __init__ method. This function is triggered whenever a client
        # creates a task for this agent. It is not re-triggered when a new
        # event is sent to the task.
        self._state = StateModel(
            input_list=[],
            turn_number=0,
        )

        # 2. Wait for the task to be completed indefinitely. If we don't do
        # this the workflow will close as soon as this function returns.
        # Temporal can run hundreds of millions of workflows in parallel,
        # so you don't need to worry about too many workflows running at once.

        # Thus, if you want this agent to field events indefinitely (or for
        # a long time) you need to wait for a condition to be met.

        await workflow.wait_condition(
            lambda: self._complete_task,
            timeout=None,  # Set a timeout if you want to prevent the task
            # from running indefinitely. Generally this is not needed.
            # Temporal can run hundreds of millions of workflows in parallel
            # and more. Only do this if you have a specific reason to do so.
        )
