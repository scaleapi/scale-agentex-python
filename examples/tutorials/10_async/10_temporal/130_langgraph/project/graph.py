"""LangGraph graph for at130-langgraph — nodes run as Temporal activities.

The ``temporalio.contrib.langgraph`` plugin runs each node where its
``execute_in`` metadata says: the LLM ``agent`` node as a durable Temporal
**activity**, the ``tools`` node inline in the **workflow**.

    START → agent → (tool calls?) → tools → agent
                 → (no tool calls?) → END

The router and tools are ``async`` so LangGraph awaits them directly — a sync
callable would be offloaded via ``run_in_executor``, which Temporal's workflow
event loop does not support.
"""

from __future__ import annotations

import os
from typing import Any, Annotated
from datetime import datetime, timedelta

_litellm_key = os.environ.get("LITELLM_API_KEY")
if _litellm_key:
    os.environ.setdefault("OPENAI_API_KEY", _litellm_key)

from typing_extensions import TypedDict

from langgraph.graph import END, START, StateGraph
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import ToolNode
from langchain_core.messages import SystemMessage
from langgraph.graph.message import add_messages

from project.tools import TOOLS

# Name this graph is registered under in the LangGraphPlugin (acp.py / run_worker.py).
GRAPH_NAME = "at130-langgraph"
MODEL_NAME = "gpt-4o"
SYSTEM_PROMPT = """You are a helpful AI assistant with access to tools.

Current date and time: {timestamp}

Be concise and use tools when they help answer the question."""


class AgentState(TypedDict):
    messages: Annotated[list[Any], add_messages]


async def agent_node(state: AgentState) -> dict[str, Any]:
    """The 'agent' node — one LLM call. Runs as a durable Temporal activity."""
    llm = ChatOpenAI(model=MODEL_NAME).bind_tools(TOOLS)
    messages = state["messages"]
    if not messages or not isinstance(messages[0], SystemMessage):
        system = SystemMessage(
            content=SYSTEM_PROMPT.format(timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        messages = [system, *messages]
    return {"messages": [await llm.ainvoke(messages)]}


async def route_after_agent(state: AgentState) -> str:
    """Go to the tools node if the model requested tools, else finish (async router)."""
    last = state["messages"][-1]
    return "tools" if getattr(last, "tool_calls", None) else END


def build_graph() -> StateGraph:
    """Build the agent graph; the LLM node runs as an activity, tools in the workflow."""
    builder = StateGraph(AgentState)
    builder.add_node(
        "agent",
        agent_node,
        metadata={"execute_in": "activity", "start_to_close_timeout": timedelta(minutes=5)},
    )
    builder.add_node("tools", ToolNode(TOOLS), metadata={"execute_in": "workflow"})
    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", route_after_agent, {"tools": "tools", END: END})
    builder.add_edge("tools", "agent")
    return builder
