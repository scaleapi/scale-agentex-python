"""
LangGraph graph definition.

Defines the state, nodes, edges, and compiles the graph.
The compiled graph is the boundary between this module and the API layer.
"""

from __future__ import annotations

from typing import Any, Annotated
from datetime import datetime
from typing_extensions import TypedDict

from langgraph.graph import START, StateGraph
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.messages import SystemMessage
from langgraph.graph.message import add_messages

from project.tools import TOOLS
from agentex.lib.adk import create_checkpointer

MODEL_NAME = "gpt-5"
SYSTEM_PROMPT = """You are a helpful AI assistant with access to tools.

Current date and time: {timestamp}

Guidelines:
- Be concise and helpful
- Use tools when they would help answer the user's question
- If you're unsure, ask clarifying questions
- Always provide accurate information
"""


class AgentState(TypedDict):
    """State schema for the agent graph."""
    messages: Annotated[list[Any], add_messages]


async def create_graph():
    """Create and compile the agent graph with checkpointer.

    Returns:
        A compiled LangGraph StateGraph ready for invocation.
    """
    llm = ChatOpenAI(
        model=MODEL_NAME,
        reasoning={"effort": "high", "summary": "auto"},
    )
    llm_with_tools = llm.bind_tools(TOOLS)

    checkpointer = await create_checkpointer()

    def agent_node(state: AgentState) -> dict[str, Any]:
        """Process the current state and generate a response."""
        messages = state["messages"]
        if not messages or not isinstance(messages[0], SystemMessage):
            system_content = SYSTEM_PROMPT.format(
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
            messages = [SystemMessage(content=system_content)] + messages
        response = llm_with_tools.invoke(messages)
        return {"messages": [response]}

    builder = StateGraph(AgentState)
    builder.add_node("agent", agent_node)
    builder.add_node("tools", ToolNode(tools=TOOLS))
    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", tools_condition, "tools")
    builder.add_edge("tools", "agent")

    return builder.compile(checkpointer=checkpointer)
