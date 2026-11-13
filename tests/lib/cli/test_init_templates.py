"""Tests for the `agentex init` project templates.

These render the Jinja templates the way the CLI does and assert that:

- every template type's declared project files exist and render,
- rendered Python parses (catches `.j2` syntax/templating regressions),
- the agent-specific context (names, workflow class) is substituted in,
- the Temporal + LangGraph template is fully wired (enum, file map, root files),
- the base Temporal template's signal handler never raises on caller input.

The Temporal + LangGraph template is the focus, but the parametrized smoke
test covers every template so a broken `.j2` anywhere is caught early.
"""

from __future__ import annotations

import ast
import importlib.util
from typing import Any
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from agentex.lib import environment_variables
from agentex.types.task import Task
from agentex.types.agent import Agent
from agentex.types.event import Event
from agentex.protocol.acp import SendEventParams
from agentex.types.data_content import DataContent
from agentex.types.text_content import TextContent
from agentex.lib.cli.commands.init import (
    TemplateType,
    get_project_context,
    create_project_structure,
)
from agentex.types.reasoning_content import ReasoningContent
from agentex.types.tool_request_content import ToolRequestContent
from agentex.types.tool_response_content import ToolResponseContent


def _context(template_type: TemplateType, use_uv: bool = True) -> dict:
    """Build the same render context the CLI assembles from user answers."""
    answers = {
        "template_type": template_type,
        "project_path": ".",
        "agent_name": "my-agent",
        "agent_directory_name": "my-agent",
        "description": "An Agentex agent",
        "use_uv": use_uv,
    }
    context = get_project_context(answers, Path("."), Path("../../"))
    context["template_type"] = template_type.value
    context["use_uv"] = use_uv
    return context


def _render_project(tmp_path: Path, template_type: TemplateType, use_uv: bool = True) -> Path:
    context = _context(template_type, use_uv=use_uv)
    create_project_structure(tmp_path, context, template_type, use_uv=use_uv)
    return tmp_path / context["project_name"]


@pytest.mark.parametrize("template_type", list(TemplateType))
def test_all_templates_render_to_valid_python(tmp_path: Path, template_type: TemplateType):
    """Every template renders, and every rendered .py file is syntactically valid."""
    project_dir = _render_project(tmp_path, template_type)

    py_files = list(project_dir.rglob("*.py"))
    assert py_files, f"{template_type.value} produced no Python files"

    for py_file in py_files:
        source = py_file.read_text()
        # Raises SyntaxError if a rendered template is broken.
        ast.parse(source, filename=str(py_file))


class TestTemporalLangGraphTemplate:
    """Focused coverage for the new Temporal + LangGraph template."""

    template_type = TemplateType.TEMPORAL_LANGGRAPH

    def test_enum_and_value(self):
        assert TemplateType.TEMPORAL_LANGGRAPH.value == "temporal-langgraph"

    def test_expected_project_files_exist(self, tmp_path: Path):
        project_dir = _render_project(tmp_path, self.template_type)
        project_pkg = project_dir / "project"
        for filename in (
            "acp.py",
            "workflow.py",
            "run_worker.py",
            "graph.py",
            "tools.py",
            "__init__.py",
        ):
            assert (project_pkg / filename).is_file(), f"missing project/{filename}"

    def test_expected_root_files_exist(self, tmp_path: Path):
        project_dir = _render_project(tmp_path, self.template_type)
        for filename in (
            "manifest.yaml",
            "README.md",
            "environments.yaml",
            ".env.example",
            ".dockerignore",
            "Dockerfile",
            "dev.ipynb",
            "pyproject.toml",
        ):
            assert (project_dir / filename).is_file(), f"missing {filename}"

    def test_workflow_class_substituted(self, tmp_path: Path):
        project_dir = _render_project(tmp_path, self.template_type)
        workflow_src = (project_dir / "project" / "workflow.py").read_text()
        # agent_name "my-agent" -> workflow class "MyAgentWorkflow"
        assert "class MyAgentWorkflow(BaseWorkflow):" in workflow_src
        assert "{{" not in workflow_src, "unrendered Jinja left in workflow.py"

    def test_nodes_run_via_langgraph_plugin(self, tmp_path: Path):
        """The defining trait: nodes run as Temporal activities via the plugin."""
        project_dir = _render_project(tmp_path, self.template_type)
        graph_src = (project_dir / "project" / "graph.py").read_text()
        # The agent (LLM) node is an activity; the tools node runs in-workflow.
        assert '"execute_in": "activity"' in graph_src
        assert '"execute_in": "workflow"' in graph_src

        # Both the worker and the ACP register the LangGraph plugin.
        worker_src = (project_dir / "project" / "run_worker.py").read_text()
        acp_src = (project_dir / "project" / "acp.py").read_text()
        assert "LangGraphPlugin" in worker_src
        assert "LangGraphPlugin" in acp_src

    def test_human_in_the_loop_and_queries_present(self, tmp_path: Path):
        project_dir = _render_project(tmp_path, self.template_type)
        workflow_src = (project_dir / "project" / "workflow.py").read_text()
        graph_src = (project_dir / "project" / "graph.py").read_text()
        # HIL: graph raises a langgraph interrupt; workflow resumes via signal + Command.
        assert "interrupt(" in graph_src
        assert "TOOLS_REQUIRING_APPROVAL" in graph_src
        assert "def provide_approval" in workflow_src
        assert "Command(resume=" in workflow_src
        assert "wait_condition" in workflow_src
        # Graph-visualization / introspection queries
        for query in ("get_status", "get_graph_mermaid", "get_graph_ascii", "get_graph_state"):
            assert query in workflow_src, f"missing query {query}"

    def test_requirements_include_langgraph_plugin_and_temporal(self, tmp_path: Path):
        # requirements.txt only renders in the non-uv variant
        project_dir = _render_project(tmp_path, self.template_type, use_uv=False)
        requirements = (project_dir / "requirements.txt").read_text()
        assert "temporalio[langgraph]>=1.27.0" in requirements
        assert "langchain-openai" in requirements


def _send_event_params(content: Any) -> SendEventParams:
    """Real ``SendEventParams``, as the ACP delivers an ``event/send`` to the workflow signal."""
    now = datetime.now(timezone.utc)
    return SendEventParams(
        agent=Agent(id="agent-1", acp_type="async", name="my-agent", description="", created_at=now, updated_at=now),
        task=Task(id="task-1"),
        event=Event(id="event-1", agent_id="agent-1", task_id="task-1", sequence_id=1, content=content),
    )


class TestTemporalTemplateSignalHandler:
    """The base Temporal template's signal handler must never raise on caller input.

    An exception raised from a signal handler fails the workflow task, and Temporal
    retries it (replaying the same signal) forever. These tests load the rendered
    ``workflow.py`` and call the handler directly, with ``adk.messages`` mocked.
    """

    @staticmethod
    def _rendered_workflow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Any, Any]:
        """Return a workflow instance from the rendered template, and the ``adk.messages`` it uses."""
        project_dir = _render_project(tmp_path, TemplateType.TEMPORAL)
        # The rendered module reads these at import time through a process-wide cache,
        # reset here; monkeypatch restores the cache and the variables afterwards.
        monkeypatch.setenv("AGENT_NAME", "my-agent")
        monkeypatch.setenv("ACP_URL", "http://localhost:8000")
        monkeypatch.setenv("WORKFLOW_NAME", "my-agent")
        monkeypatch.setattr(environment_variables, "refreshed_environment_variables", None)

        spec = importlib.util.spec_from_file_location(
            "rendered_temporal_workflow", project_dir / "project" / "workflow.py"
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Build the instance without Temporal: skip __init__ and set what it would set.
        wf = module.MyAgentWorkflow.__new__(module.MyAgentWorkflow)
        wf.display_name = "my-agent"
        wf._complete_task = False
        return wf, module.adk.messages

    async def test_event_without_content_is_ignored(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        wf, messages = self._rendered_workflow(tmp_path, monkeypatch)
        with patch.object(messages, "create", new=AsyncMock()) as create:
            await wf.on_task_event_send(_send_event_params(None))

        create.assert_not_awaited()

    @pytest.mark.parametrize(
        "content",
        [
            pytest.param(TextContent(author="user", content="Hello!"), id="text"),
            pytest.param(DataContent(author="user", data={}), id="data"),
            pytest.param(ReasoningContent(author="user", summary=["thinking"], type="reasoning"), id="reasoning"),
            pytest.param(
                ToolRequestContent(author="user", name="get_weather", tool_call_id="call-1", arguments={}),
                id="tool-request",
            ),
            pytest.param(
                ToolResponseContent(author="user", name="get_weather", tool_call_id="call-1", content={"k": "v"}),
                id="tool-response-dict",
            ),
            pytest.param(
                ToolResponseContent(author="user", name="get_weather", tool_call_id="call-1", content=[1, 2]),
                id="tool-response-list",
            ),
        ],
    )
    async def test_event_is_echoed_then_answered(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, content: Any):
        wf, messages = self._rendered_workflow(tmp_path, monkeypatch)
        with patch.object(messages, "create", new=AsyncMock()) as create:
            await wf.on_task_event_send(_send_event_params(content))

        assert create.await_count == 2
        echo, reply = create.await_args_list
        assert echo.kwargs == {"task_id": "task-1", "content": content}
        assert reply.kwargs["content"].author == "agent"
