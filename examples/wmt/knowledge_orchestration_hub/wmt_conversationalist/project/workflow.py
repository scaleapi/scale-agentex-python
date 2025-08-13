import os
from typing import Dict, List, override
from dotenv import load_dotenv

from agentex.lib.utils.model_utils import BaseModel
from mcp import StdioServerParameters
from temporalio import workflow

from agentex.lib import adk
from agentex.lib.types.acp import CreateTaskParams, SendEventParams
from agentex.lib.core.temporal.workflows.workflow import BaseWorkflow
from agentex.lib.core.temporal.types.workflow import SignalName
from agentex.lib.utils.logging import make_logger
from agentex.lib.environment_variables import EnvironmentVariables
from agentex.types.text_content import TextContent

from auth.openai import set_openai_api_key_from_secrets_if_not_available_in_env
from tools import AVAILABLE_TOOLS

environment_variables = EnvironmentVariables.refresh()
load_dotenv(dotenv_path=".env")


if environment_variables.WORKFLOW_NAME is None:
    raise ValueError("Environment variable WORKFLOW_NAME is not set")

if environment_variables.AGENT_NAME is None:
    raise ValueError("Environment variable AGENT_NAME is not set")

logger = make_logger(__name__)
set_openai_api_key_from_secrets_if_not_available_in_env()


class StateModel(BaseModel):
    input_list: List[Dict]
    turn_number: int


def get_openai_api_key():
    """Get OpenAI API key from environment."""
    return os.environ.get("OPENAI_API_KEY", "")


# MCP Servers - Web Search and Confluence
MCP_SERVERS = [
    StdioServerParameters(
        command="uvx",
        args=["openai-websearch-mcp"],
        env={"OPENAI_API_KEY": get_openai_api_key()},
    ),
    # Atlassian/Confluence MCP server (matches Cursor config)
    StdioServerParameters(
        command="npx",
        args=["-y", "mcp-remote", "https://mcp.atlassian.com/v1/sse"],
    ),
]


@workflow.defn(name=environment_variables.WORKFLOW_NAME)
class WmtConversationalistWorkflow(BaseWorkflow):
    """
    Knowledge Hub conversational agent with web search, Confluence access, and deep research artifact search.
    Based on the 010_agent_chat template with custom tools.
    """

    def __init__(self):
        super().__init__(display_name=environment_variables.AGENT_NAME)
        self._complete_task = False
        self._state = None

    @workflow.signal(name=SignalName.RECEIVE_EVENT)
    @override
    async def on_task_event_send(self, params: SendEventParams) -> None:
        logger.info(f"Received task message instruction: {params}")

        if not params.event.content:
            return
        if params.event.content.type != "text":
            raise ValueError(f"Expected text message, got {params.event.content.type}")

        if params.event.content.author != "user":
            raise ValueError(
                f"Expected user message, got {params.event.content.author}"
            )

        # Increment the turn number
        self._state.turn_number += 1
        # Add the new user message to the message history
        self._state.input_list.append(
            {"role": "user", "content": params.event.content.content}
        )

        async with adk.tracing.span(
            trace_id=params.task.id,
            name=f"Knowledge Hub Turn {self._state.turn_number}",
            input=self._state,
        ) as span:
            # Echo back the user's message so it shows up in the UI
            await adk.messages.create(
                task_id=params.task.id,
                trace_id=params.task.id,
                content=params.event.content,
                parent_span_id=span.id if span else None,
            )

            # Call the OpenAI agent with MCP servers and custom tools
            run_result = await adk.providers.openai.run_agent_streamed_auto_send(
                task_id=params.task.id,
                trace_id=params.task.id,
                input_list=self._state.input_list,
                mcp_server_params=MCP_SERVERS,
                tools=[t.to_oai_function_tool() for t in AVAILABLE_TOOLS],
                agent_name="Knowledge Hub Assistant",
                agent_instructions="""You are a knowledgeable conversational assistant for a Knowledge Hub system with access to multiple information sources.

**Your capabilities:**

🔍 **Web Search**: You can search the web for current information and real-time data
📚 **Confluence Access**: You have access to organizational Confluence spaces and documentation
🧠 **Deep Research Artifacts**: You can search previously generated comprehensive research reports

**Guidelines:**
- Always cite sources when providing information
- Use web search for current events or information not in organizational systems
- Check Confluence for internal documentation, processes, and organizational knowledge
- Search deep research artifacts for comprehensive analysis on topics that may have been previously researched
- Be conversational but precise
- Suggest follow-up questions when appropriate
- If you can't find information in one source, try another

**Tool Usage:**
- Use web search for general queries and current information
- Use Confluence tools for organizational/internal information
- Use `search_deep_research_artifacts` to find previously generated research reports
- Combine information from multiple sources when helpful

How can I help you explore the Knowledge Hub today?""",
                parent_span_id=span.id if span else None,
                model="openai/gpt-4o-mini",
            )
            self._state.input_list = run_result.final_input_list

            # Set the span output to the state for the next turn
            span.output = self._state

    @workflow.run
    @override
    async def on_task_create(self, params: CreateTaskParams) -> None:
        logger.info(f"Received task create params: {params}")

        # Initialize the state
        self._state = StateModel(
            input_list=[],
            turn_number=0,
        )

        # Send welcome message
        await adk.messages.create(
            task_id=params.task.id,
            content=TextContent(
                author="agent",
                content="""Hello! I'm your Knowledge Hub Assistant. I have access to:

🌐 **Web Search**: Current information and real-time data
📚 **Confluence**: Organizational documentation and internal knowledge  
🧠 **Research Artifacts**: Previously generated comprehensive research reports

I can help you with:
- Finding current information through web search
- Accessing internal documentation from Confluence
- Searching through existing research reports and analysis
- Combining information from multiple sources
- Answering questions with proper citations

What would you like to explore today?""",
            ),
        )

        # Wait for the task to be completed indefinitely
        await workflow.wait_condition(
            lambda: self._complete_task,
            timeout=None,
        )
