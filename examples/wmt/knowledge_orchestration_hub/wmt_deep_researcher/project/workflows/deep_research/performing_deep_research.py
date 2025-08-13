import os
from datetime import datetime
from typing import Optional, override

from agentex.lib import adk
from agentex.lib.sdk.state_machine.state_machine import StateMachine
from mcp import StdioServerParameters

from agentex.lib.sdk.state_machine.state_workflow import StateWorkflow
from agentex.types.text_content import TextContent
from agentex.lib.utils.logging import make_logger

from project.state_machines.deep_research import DeepResearchData, DeepResearchState
from project.auth.openai import (
    set_openai_api_key_from_secrets_if_not_available_in_env,
)

logger = make_logger(__name__)
set_openai_api_key_from_secrets_if_not_available_in_env()

MCP_SERVERS = [
    StdioServerParameters(
        command="uvx",
        args=["openai-websearch-mcp"],
        env={"OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY", "")},
    ),
    # Atlassian/Confluence MCP server (matches Cursor config)
    StdioServerParameters(
        command="npx",
        args=["-y", "mcp-remote", "https://mcp.atlassian.com/v1/sse"],
    ),
]


class PerformingDeepResearchWorkflow(StateWorkflow):
    """Workflow for performing deep research."""

    @override
    async def execute(
        self,
        state_machine: StateMachine,
        state_machine_data: Optional[DeepResearchData] = None,
    ) -> str:
        """Execute the workflow."""
        if state_machine_data is None:
            return DeepResearchState.WAITING_FOR_USER_INPUT

        if not state_machine_data.user_query:
            return DeepResearchState.WAITING_FOR_USER_INPUT

        # Increment research iteration
        state_machine_data.research_iteration += 1

        # Create research instruction based on whether this is the first
        # iteration or a continuation
        if state_machine_data.research_iteration == 1:
            initial_instruction = f"Initial Query: {state_machine_data.user_query}"

            # Notify user that deep research is starting
            if state_machine_data.task_id and state_machine_data.current_span:
                await adk.messages.create(
                    task_id=state_machine_data.task_id,
                    content=TextContent(
                        author="agent",
                        content=(
                            "Starting deep research process based on your " "query..."
                        ),
                    ),
                    trace_id=state_machine_data.task_id,
                    parent_span_id=state_machine_data.current_span.id,
                )
        else:
            report_text = (
                f"Current Research Report "
                f"(Iteration {state_machine_data.research_iteration - 1}):\n"
                f"{state_machine_data.research_report}"
            )
            initial_instruction = (
                f"Initial Query: {state_machine_data.user_query}\n" f"{report_text}"
            )

            # Notify user that research is continuing
            if state_machine_data.task_id and state_machine_data.current_span:
                iteration_num = state_machine_data.research_iteration
                message = (
                    f"Continuing deep research (iteration {iteration_num}) "
                    "to expand and refine the research report..."
                )
                await adk.messages.create(
                    task_id=state_machine_data.task_id,
                    content=TextContent(
                        author="agent",
                        content=message,
                    ),
                    trace_id=state_machine_data.task_id,
                    parent_span_id=state_machine_data.current_span.id,
                )

        # Fetch the current time in human readable format
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z")

        # Deep Research Loop
        if not state_machine_data.agent_input_list:
            content = (
                f"{initial_instruction}\n\n"
                "You should now perform a depth search to get a more "
                "detailed understanding of the topic.\n\n"
                f"The current time is {current_time}.\n"
            )
            state_machine_data.agent_input_list = [{"role": "user", "content": content}]

        if state_machine_data.task_id and state_machine_data.current_span:
            iteration_note = (
                f"If this is a continuation of previous research "
                f"(iteration {state_machine_data.research_iteration}), "
                f"focus on:\n"
                "1. Expanding areas that need more detail\n"
                "2. Adding new relevant information discovered\n"
                "3. Removing outdated or incorrect information\n"
                "4. Improving the overall structure and clarity of the report"
            )

            instructions = (
                "You are a deep research expert that can search the web for "
                "information.\nYou should use the tools you have access to to "
                "write an extensive report on the users query.\n\n"
                "You must use the web search tool at least 10 times before "
                "writing your report.\nUse the fetch tool to open links you "
                "want to read.\nThen use web search again repeatedly to dig "
                "deeper into the most promising areas of search results.\n\n"
                "Be very targeted with your searches, make sure all search "
                "queries are relevant to either the initial user query or dig "
                "deeper into the most promising areas of search results. All "
                "searches should tie back to the original query though. "
                "Remember your searches are stateless, so there is no context "
                "shared between search queries.\n\n"
                "Always cite your sources in the format [source](link). Do "
                "not hallucinate. Your latent information is not likely to be "
                f"up to date.\n\n{iteration_note}"
            )

            result = await adk.providers.openai.run_agent_streamed_auto_send(
                task_id=state_machine_data.task_id,
                trace_id=state_machine_data.task_id,
                input_list=state_machine_data.agent_input_list,
                mcp_server_params=MCP_SERVERS,
                agent_name="Deep Research Agent",
                agent_instructions=instructions,
                parent_span_id=state_machine_data.current_span.id,
                mcp_timeout_seconds=180,
            )

            # Update state with conversation history
            state_machine_data.agent_input_list = result.final_input_list

            # Extract the research report from the last assistant message
            if result.final_input_list:
                for message in reversed(result.final_input_list):
                    if message.get("role") == "assistant":
                        content = message.get("content", "")
                        state_machine_data.research_report = content
                        break

        # Keep the research data active for future iterations

        if state_machine_data.task_id and state_machine_data.current_span:
            await adk.tracing.end_span(
                trace_id=state_machine_data.task_id,
                span=state_machine_data.current_span,
            )
        state_machine_data.current_span = None

        # Transition to waiting for user input state
        return DeepResearchState.WAITING_FOR_USER_INPUT
