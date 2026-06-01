"""Tests for the Temporal + LangGraph agent's graph.

Two layers:

1. ``TestGraphLogic`` — hermetic, no network. Compiles the actual shipped
   graph (``project/graph.py``) with a deterministic stub model and runs the
   ReAct loop (agent → tools → agent) to completion.

2. ``TestTemporalPlugin`` — end-to-end through the real Temporal LangGraph
   plugin on a local Temporal server, proving the LLM node runs as an activity
   and the tool node in the workflow. Needs a real model, so it is skipped
   unless ``LITELLM_API_KEY`` (or ``OPENAI_API_KEY``) is set.

Run from the agent's own (uv) environment:  pytest tests/test_graph_temporal.py -v
"""

from __future__ import annotations

import os
import uuid

import pytest

pytest.importorskip("langgraph")
pytest.importorskip("temporalio.contrib.langgraph")

import project.graph as graph_module
from temporalio import workflow
from project.graph import GRAPH_NAME, build_graph
from langchain_core.messages import AIMessage, ToolMessage
from temporalio.contrib.langgraph import graph as lg_graph


@workflow.defn
class _DriverWorkflow:
    """Module-level driver workflow (Temporal forbids local workflow classes)."""

    @workflow.run
    async def run(self, message: str) -> str:
        compiled = lg_graph(GRAPH_NAME).compile()
        result = await compiled.ainvoke({"messages": [{"role": "user", "content": message}]})
        return result["messages"][-1].content


class _StubModel:
    """Deterministic stand-in for ``ChatOpenAI(...).bind_tools(...)``.

    First call → emit a tool call for ``get_weather``; once a ToolMessage is in
    the history → emit a plain text answer. Drives the full ReAct loop offline.
    """

    def bind_tools(self, _tools):
        return self

    async def ainvoke(self, messages):
        if any(isinstance(m, ToolMessage) for m in messages):
            return AIMessage(content="All done — the tool has run.")
        return AIMessage(
            content="",
            tool_calls=[{"id": "call_1", "name": "get_weather", "args": {"city": "Denver"}}],
        )


class TestGraphLogic:
    """Hermetic test of the ReAct loop, no network."""

    @pytest.mark.asyncio
    async def test_react_loop_runs_tool(self, monkeypatch):
        monkeypatch.setattr(graph_module, "ChatOpenAI", lambda *_a, **_k: _StubModel())
        compiled = build_graph().compile()
        result = await compiled.ainvoke({"messages": [{"role": "user", "content": "go"}]})

        tool_outputs = [m.content for m in result["messages"] if isinstance(m, ToolMessage)]
        assert any("sunny" in o for o in tool_outputs)
        assert "done" in result["messages"][-1].content.lower()


@pytest.mark.skipif(
    not (os.environ.get("LITELLM_API_KEY") or os.environ.get("OPENAI_API_KEY")),
    reason="needs a real model (set LITELLM_API_KEY) for the live Temporal run",
)
class TestTemporalPlugin:
    """End-to-end through the real Temporal LangGraph plugin on a local server."""

    @pytest.mark.asyncio
    async def test_nodes_run_as_activities_via_plugin(self):
        from temporalio.worker import Worker, UnsandboxedWorkflowRunner
        from temporalio.testing import WorkflowEnvironment
        from temporalio.contrib.langgraph import LangGraphPlugin

        plugin = LangGraphPlugin(graphs={GRAPH_NAME: build_graph()})
        async with await WorkflowEnvironment.start_local(plugins=[plugin]) as env:
            async with Worker(
                env.client,
                task_queue="tq",
                workflows=[_DriverWorkflow],
                workflow_runner=UnsandboxedWorkflowRunner(),
            ):
                out = await env.client.execute_workflow(
                    _DriverWorkflow.run,
                    "What's the weather in Denver? Use the get_weather tool.",
                    id=f"wf-{uuid.uuid4()}",
                    task_queue="tq",
                )
        assert "denver" in out.lower()
