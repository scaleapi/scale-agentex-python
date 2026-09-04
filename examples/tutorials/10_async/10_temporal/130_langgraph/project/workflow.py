"""Temporal workflow for at130-langgraph.

Each turn the workflow runs the LangGraph graph (``project/graph.py``) via the
``temporalio.contrib.langgraph`` plugin. The plugin runs the LLM ``agent`` node
as a durable Temporal activity and the ``tools`` node inline in the workflow.

Multi-turn memory is kept on the workflow instance (``self._messages``) — it's
durable and replay-safe for free, so no checkpoint database is needed.
"""

from __future__ import annotations

import json
from typing import Any

from temporalio import workflow
from temporalio.contrib.langgraph import graph as lg_graph

from agentex.lib import adk
from project.graph import GRAPH_NAME
from agentex.lib.adk import emit_langgraph_messages
from agentex.protocol.acp import SendEventParams, CreateTaskParams
from agentex.lib.utils.logging import make_logger
from agentex.types.text_content import TextContent
from agentex.lib.environment_variables import EnvironmentVariables
from agentex.lib.core.temporal.types.workflow import SignalName
from agentex.lib.core.temporal.workflows.workflow import BaseWorkflow

environment_variables = EnvironmentVariables.refresh()

if environment_variables.WORKFLOW_NAME is None:
    raise ValueError("Environment variable WORKFLOW_NAME is not set")
if environment_variables.AGENT_NAME is None:
    raise ValueError("Environment variable AGENT_NAME is not set")

logger = make_logger(__name__)


@workflow.defn(name=environment_variables.WORKFLOW_NAME)
class AtHarnessLanggraphWorkflow(BaseWorkflow):
    """Runs the LangGraph agent each turn; its nodes run as Temporal activities."""

    def __init__(self) -> None:
        super().__init__(display_name=environment_variables.AGENT_NAME)
        self._complete_task = False
        self._messages: list[Any] = []
        self._emitted = 0

    @workflow.signal(name=SignalName.RECEIVE_EVENT)
    async def on_task_event_send(self, params: SendEventParams) -> None:
        """Echo the user's message, run the graph, surface the new messages."""
        await adk.messages.create(task_id=params.task.id, content=params.event.content)
        self._messages.append({"role": "user", "content": params.event.content.content})

        compiled = lg_graph(GRAPH_NAME).compile()
        result = await compiled.ainvoke({"messages": self._messages})
        self._messages = result["messages"]

        await emit_langgraph_messages(self._messages[self._emitted :], params.task.id)
        self._emitted = len(self._messages)

    @workflow.signal
    async def complete_task_signal(self) -> None:
        self._complete_task = True

    @workflow.run
    async def on_task_create(self, params: CreateTaskParams) -> str:
        await adk.messages.create(
            task_id=params.task.id,
            content=TextContent(
                author="agent",
                content=(
                    f"Task initialized with params:\n{json.dumps(params.params, indent=2)}\n\n"
                    "Send me a message and I'll respond using a LangGraph agent whose nodes "
                    "run as durable Temporal activities."
                ),
            ),
        )
        await workflow.wait_condition(lambda: self._complete_task, timeout=None)
        return "Task completed"
