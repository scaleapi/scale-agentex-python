import os
from typing import override
from datetime import timedelta
from dataclasses import asdict, dataclass

from agents import TResponseInputItem
from dotenv import load_dotenv
from agents.mcp import MCPServerStdioParams
from temporalio import workflow
from temporalio.common import RetryPolicy

from agentex.lib import adk
from agentex.lib.types.acp import SendEventParams, CreateTaskParams
from agentex.lib.types.tracing import SGPTracingProcessorConfig
from agentex.lib.utils.logging import make_logger
from project.special_run_agent import SPECIAL_RUN_AGENT_ACTIVITY_NAME, SpecialRunAgentParams, SpecialRunAgentResult
from agentex.types.text_content import TextContent
from agentex.lib.environment_variables import EnvironmentVariables
from agentex.lib.core.temporal.types.workflow import SignalName
from agentex.lib.core.temporal.workflows.workflow import BaseWorkflow
from agentex.lib.core.tracing.tracing_processor_manager import add_tracing_processor_config

environment_variables = EnvironmentVariables.refresh()
load_dotenv(dotenv_path=".env")

add_tracing_processor_config(
    SGPTracingProcessorConfig(
        sgp_api_key=os.environ.get("SCALE_GP_API_KEY", ""),
        sgp_account_id=os.environ.get("SCALE_GP_ACCOUNT_ID", ""),
    )
)

if environment_variables is None:
    raise ValueError("Environment variables could not be loaded")

if environment_variables.WORKFLOW_NAME is None:
    raise ValueError("Environment variable WORKFLOW_NAME is not set")

if environment_variables.AGENT_NAME is None:
    raise ValueError("Environment variable AGENT_NAME is not set")

WORKFLOW_NAME = environment_variables.WORKFLOW_NAME
AGENT_NAME = environment_variables.AGENT_NAME


@dataclass
class State:
    input_list: list[TResponseInputItem]
    turn_number: int


@workflow.defn(name=WORKFLOW_NAME)
class At011CustomAgentChatWorkflow(BaseWorkflow):
    """
    Simple async workflow for AgentEx Temporal agents with a custom Temporal activity.
    """

    def __init__(self) -> None:
        super().__init__(display_name=AGENT_NAME)
        self._logger = make_logger(__name__)
        self._complete_task = False

        self._mcp_servers: list[MCPServerStdioParams] = [
            {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"],
            },
            {
                "command": "uvx",
                "args": ["openai-websearch-mcp"],
                "env": {"OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY", "")},
            },
        ]

        # Initialize the state. You can either do this here or in the on_task_create method.
        self._state = State(
            input_list=[],
            turn_number=0,
        )

    @workflow.signal(name=SignalName.RECEIVE_EVENT)
    @override
    async def on_task_event_send(self, params: SendEventParams) -> None:
        self._logger.info(f"Received task message instruction: {params}")

        if not params.event.content:
            return
        if params.event.content.type != "text":
            raise ValueError(f"Expected text message, got {params.event.content.type}")

        if params.event.content.author != "user":
            raise ValueError(f"Expected user message, got {params.event.content.author}")

        # Increment the turn number
        self._state.turn_number += 1
        # Add the new user message to the message history
        self._state.input_list.append({"role": "user", "content": params.event.content.content})

        async with adk.tracing.span(
            trace_id=params.task.id, name=f"Turn {self._state.turn_number}", input=asdict(self._state)
        ) as span:
            # Echo back the user's message so it shows up in the UI. This is not done by default so the agent developer has full control over what is shown to the user.
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
                        content="Hey, sorry I'm unable to respond to your message because you're running this example without an OpenAI API key. Please set the OPENAI_API_KEY environment variable to run this example. Do this by either by adding a .env file to the project/ directory or by setting the environment variable in your terminal.",
                    ),
                    parent_span_id=span.id if span else None,
                )

            # Custom activity that generates a response
            run_result: SpecialRunAgentResult = await workflow.execute_activity(
                activity=SPECIAL_RUN_AGENT_ACTIVITY_NAME,
                arg=SpecialRunAgentParams(
                    task_id=params.task.id,
                    input_list=self._state.input_list,
                    mcp_server_params=self._mcp_servers,
                    agent_name="Tool-Enabled Assistant",
                    agent_instructions="You are a helpful assistant that can answer questions using various tools.\n"
                    "You have access to sequential thinking and web search capabilities through MCP servers.\n"
                    "Use these tools when appropriate to provide accurate and well-reasoned responses.",
                    trace_id=params.task.id,
                    parent_span_id=span.id if span else None,
                ),
                start_to_close_timeout=timedelta(seconds=60),
                retry_policy=RetryPolicy(maximum_attempts=0),
                heartbeat_timeout=timedelta(seconds=30),
            )

            self._state.input_list = run_result["final_input_list"]

            # Set the span output to the state for the next turn
            if span is not None:
                span.output = asdict(self._state)

    @workflow.run
    @override
    async def on_task_create(self, params: CreateTaskParams) -> None:
        """
        This method is triggered whenever a client creates a task for this agent.
        It is not re-triggered when a new event is sent to the task.
        """

        self._logger.info(f"Received task create params: {params}")

        # Wait for the task to be completed indefinitely. If we don't do this the workflow will close as soon as this function returns. Temporal can run hundreds of millions of workflows in parallel, so you don't need to worry about too many workflows running at once.

        # Thus, if you want this agent to field events indefinitely (or for a long time) you need to wait for a condition to be met.

        await workflow.wait_condition(
            lambda: self._complete_task,
            timeout=None,  # Set a timeout if you want to prevent the task from running indefinitely. Generally this is not needed. Temporal can run hundreds of millions of workflows in parallel and more. Only do this if you have a specific reason to do so.
        )
