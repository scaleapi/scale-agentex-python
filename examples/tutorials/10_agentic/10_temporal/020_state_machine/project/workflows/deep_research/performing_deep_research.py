from datetime import datetime
import os
from typing import Optional, override

from agentex.lib import adk
from agentex.lib.sdk.state_machine.state_machine import StateMachine
from mcp import StdioServerParameters

from agentex.lib.sdk.state_machine.state_workflow import StateWorkflow
from agentex.types.text_content import TextContent
from agentex.lib.utils.logging import make_logger

from state_machines.deep_research import DeepResearchData, DeepResearchState

logger = make_logger(__name__)

MCP_SERVERS = [
    StdioServerParameters(
        command="uvx",
        args=["mcp-server-time", "--local-timezone", "America/Los_Angeles"],
    ),
    StdioServerParameters(
        command="uvx",
        args=["openai-websearch-mcp"],
        env={
            "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY", "")
        }
    ),
    StdioServerParameters(
        command="uvx",
        args=["mcp-server-fetch"],
    ),
]

class PerformingDeepResearchWorkflow(StateWorkflow):
    """Workflow for performing deep research."""

    @override
    async def execute(self, state_machine: StateMachine, state_machine_data: Optional[DeepResearchData] = None) -> str:
        """Execute the workflow."""
        if state_machine_data is None:
            return DeepResearchState.CLARIFYING_USER_QUERY
            
        if not state_machine_data.user_query:
            return DeepResearchState.CLARIFYING_USER_QUERY

        # Construct initial research instruction
        follow_up_qa_str = ""
        for q, r in zip(state_machine_data.follow_up_questions, state_machine_data.follow_up_responses):
            follow_up_qa_str += f"Q: {q}\nA: {r}\n"
        
        # Increment research iteration
        state_machine_data.research_iteration += 1
        
        # Create research instruction based on whether this is the first iteration or a continuation
        if state_machine_data.research_iteration == 1:
            initial_instruction = (
                f"Initial Query: {state_machine_data.user_query}\n"
                f"Follow-up Q&A:\n{follow_up_qa_str}"
            )
            
            # Notify user that deep research is starting
            if state_machine_data.task_id and state_machine_data.current_span:
                await adk.messages.create(
                    task_id=state_machine_data.task_id,
                    content=TextContent(
                            author="agent",
                            content="Starting deep research process based on your query and follow-up responses...",
                        ),
                    trace_id=state_machine_data.task_id,
                    parent_span_id=state_machine_data.current_span.id,
                )
        else:
            initial_instruction = (
                f"Initial Query: {state_machine_data.user_query}\n"
                f"Follow-up Q&A:\n{follow_up_qa_str}\n"
                f"Current Research Report (Iteration {state_machine_data.research_iteration - 1}):\n{state_machine_data.research_report}"
            )
            
            # Notify user that research is continuing
            if state_machine_data.task_id and state_machine_data.current_span:
                await adk.messages.create(
                    task_id=state_machine_data.task_id,
                    content=TextContent(
                            author="agent",
                            content=f"Continuing deep research (iteration {state_machine_data.research_iteration}) to expand and refine the research report...",
                        ),
                    trace_id=state_machine_data.task_id,
                    parent_span_id=state_machine_data.current_span.id,
                )

        # Fetch the current time in human readable format
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z")

        # Deep Research Loop
        if not state_machine_data.agent_input_list:
            state_machine_data.agent_input_list = [
                {"role": "user", "content": f"""
Here is my initial query, clarified with the following follow-up questions and answers:
{initial_instruction}

You should now perform a depth search to get a more detailed understanding of the most promising areas.

The current time is {current_time}.
"""}
            ]

        if state_machine_data.task_id and state_machine_data.current_span:
            result = await adk.providers.openai.run_agent_streamed_auto_send(
                task_id=state_machine_data.task_id,
                trace_id=state_machine_data.task_id,
                input_list=state_machine_data.agent_input_list,
                mcp_server_params=MCP_SERVERS,
                agent_name="Deep Research Agent",
                agent_instructions=f"""You are a deep research expert that can search the web for information.
You should use the tools you have access to to write an extensive report on the users query.

You must use the web search tool at least 10 times before writing your report.
Use the fetch tool to open links you want to read.
Then use web search again repeatedly to dig deeper into the most promising areas of search results.

Be very targeted with your searches, make sure all search queries are relevant to either the initial user query or dig deeper into the most promising areas of search results. All searches should tie back to the original query though. Remember your searches are stateless, so there is no context shared between search queries.

Always cite your sources in the format [source](link). Do not hallucinate. Your latent information is not likely to be up to date.

If this is a continuation of previous research (iteration {state_machine_data.research_iteration}), focus on:
1. Expanding areas that need more detail
2. Adding new relevant information discovered
3. Removing outdated or incorrect information
4. Improving the overall structure and clarity of the report
""",
                parent_span_id=state_machine_data.current_span.id,
                mcp_timeout_seconds=180,
            )
            
            # Update state with conversation history
            state_machine_data.agent_input_list = result.final_input_list
            
            # Extract the research report from the last assistant message
            if result.final_input_list:
                for message in reversed(result.final_input_list):
                    if message.get("role") == "assistant":
                        state_machine_data.research_report = message.get("content", "")
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