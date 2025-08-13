import os
import sys
from typing import Any, Dict, List
from dotenv import load_dotenv
from mcp import StdioServerParameters

# === DEBUG SETUP (AgentEx CLI Debug Support) ===
if os.getenv("AGENTEX_DEBUG_ENABLED") == "true":
    try:
        import debugpy

        debug_port = int(os.getenv("AGENTEX_DEBUG_PORT", "5679"))
        debug_type = os.getenv("AGENTEX_DEBUG_TYPE", "acp")
        wait_for_attach = (
            os.getenv("AGENTEX_DEBUG_WAIT_FOR_ATTACH", "false").lower() == "true"
        )

        # Configure debugpy
        debugpy.configure(subProcess=False)
        debugpy.listen(debug_port)

        print(f"🐛 [{debug_type.upper()}] Debug server listening on port {debug_port}")

        if wait_for_attach:
            print(f"⏳ [{debug_type.upper()}] Waiting for debugger to attach...")
            debugpy.wait_for_client()
            print(f"✅ [{debug_type.upper()}] Debugger attached!")
        else:
            print(f"📡 [{debug_type.upper()}] Ready for debugger attachment")

    except ImportError:
        print("❌ debugpy not available. Install with: pip install debugpy")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Debug setup failed: {e}")
        sys.exit(1)
# === END DEBUG SETUP ===

from agentex.lib import adk
from agentex.lib.sdk.fastacp.fastacp import FastACP
from agentex.lib.types.acp import CancelTaskParams, CreateTaskParams, SendEventParams
from agentex.lib.types.fastacp import AgenticACPConfig
from agentex.lib.utils.logging import make_logger
from agentex.lib.utils.model_utils import BaseModel
from agentex.types.text_content import TextContent

from .auth.openai import set_openai_api_key_from_secrets_if_not_available_in_env
from .tools import AVAILABLE_TOOLS

load_dotenv(dotenv_path=".env")

logger = make_logger(__name__)
set_openai_api_key_from_secrets_if_not_available_in_env()


class StateModel(BaseModel):
    input_list: List[Dict[str, Any]]
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


# Create an ACP server
# !!! Warning: Because "Agentic" ACPs are designed to be fully
# asynchronous, race conditions can occur if parallel events are sent.
# It is highly recommended to use the "temporal" type in the
# AgenticACPConfig instead to handle complex use cases. The "base" ACP
# is only designed to be used for simple use cases and for learning purposes.
acp = FastACP.create(
    acp_type="agentic",
    config=AgenticACPConfig(type="base"),
)


@acp.on_task_create
async def handle_task_create(params: CreateTaskParams):
    """
    Initialize the Knowledge Hub conversational agent task.
    """
    logger.info(f"Received task create params: {params}")

    # Initialize the state
    state = StateModel(
        input_list=[],
        turn_number=0,
    )
    await adk.state.create(
        task_id=params.task.id, agent_id=params.agent.id, state=state
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


@acp.on_task_event_send
async def handle_event_send(params: SendEventParams):
    """
    Handle user messages and provide knowledge hub assistance.
    """
    # !!! Warning: Because "Agentic" ACPs are designed to be fully
    # asynchronous, race conditions can occur if parallel events are sent.
    # It is highly recommended to use the "temporal" type in the
    # AgenticACPConfig instead to handle complex use cases. The "base" ACP
    # is only designed to be used for simple use cases and for learning
    # purposes.

    logger.info(f"Received task message instruction: {params}")

    #########################################################
    # 1. Validate the event content.
    #########################################################
    if not params.event.content:
        return

    if params.event.content.type != "text":
        raise ValueError(f"Expected text message, got {params.event.content.type}")

    if params.event.content.author != "user":
        raise ValueError(f"Expected user message, got {params.event.content.author}")

    #########################################################
    # 2. Echo back the user's message.
    #########################################################
    await adk.messages.create(
        task_id=params.task.id,
        trace_id=params.task.id,
        content=params.event.content,
    )

    #########################################################
    # 3. If the OpenAI API key is not set, send a message to the user to let them know.
    #########################################################
    if not os.environ.get("OPENAI_API_KEY"):
        await adk.messages.create(
            task_id=params.task.id,
            trace_id=params.task.id,
            content=TextContent(
                author="agent",
                content="Hey, sorry I'm unable to respond to your message "
                "because you're running this example without an OpenAI API key. "
                "Please set the OPENAI_API_KEY environment variable to run "
                "this example. Do this by either by adding a .env file to the "
                "project/ directory or by setting the environment variable in "
                "your terminal.",
            ),
        )
        return

    #########################################################
    # 4. Retrieve the task state.
    #########################################################
    task_state = await adk.state.get_by_task_and_agent(
        task_id=params.task.id, agent_id=params.agent.id
    )
    if task_state is None or task_state.state is None:
        logger.error("Task state not found")
        return
    state = StateModel.model_validate(task_state.state)

    # Increment the turn number and add the new user message to the message history
    state.turn_number += 1
    state.input_list.append({"role": "user", "content": params.event.content.content})

    #########################################################
    # 5. Use OpenAI agent with MCP servers and custom tools for advanced capabilities
    #########################################################
    async with adk.tracing.span(
        trace_id=params.task.id,
        name=f"Knowledge Hub Turn {state.turn_number}",
        input=state,
    ) as span:
        # Call the OpenAI agent with MCP servers and custom tools
        agent_instructions = """You are a knowledgeable conversational assistant for a Knowledge Hub system with access to multiple information sources.

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

How can I help you explore the Knowledge Hub today?"""

        run_result = await adk.providers.openai.run_agent_streamed_auto_send(
            task_id=params.task.id,
            trace_id=params.task.id,
            input_list=state.input_list,
            mcp_server_params=MCP_SERVERS,
            tools=AVAILABLE_TOOLS,
            agent_name="Knowledge Hub Assistant",
            agent_instructions=agent_instructions,
            parent_span_id=span.id if span else None,
            model="openai/gpt-4o-mini",
        )
        # Update the state with the conversation history
        if hasattr(run_result, "final_input_list"):
            state.input_list = run_result.final_input_list

        # Set the span output to the state for the next turn
        if span is not None:
            span.output = state.model_dump()

    #########################################################
    # 6. Store the updated state for the next turn
    #########################################################
    await adk.state.update(
        state_id=task_state.id,
        task_id=params.task.id,
        agent_id=params.agent.id,
        state=state,
        trace_id=params.task.id,
    )


@acp.on_task_cancel
async def handle_task_cancel(params: CancelTaskParams):
    """Default task cancel handler"""
    logger.info(f"Task canceled: {params.task}")
