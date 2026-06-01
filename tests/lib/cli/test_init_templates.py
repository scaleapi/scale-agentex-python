"""Tests for the `agentex init` project templates.

These render the Jinja templates the way the CLI does and assert that:

- every template type's declared project files exist and render,
- rendered Python parses (catches `.j2` syntax/templating regressions),
- the agent-specific context (names, workflow class) is substituted in,
- the Temporal + LangGraph template is fully wired (enum, file map, root files).

The Temporal + LangGraph template is the focus, but the parametrized smoke
test covers every template so a broken `.j2` anywhere is caught early.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from agentex.lib.cli.commands.init import (
    TemplateType,
    get_project_context,
    create_project_structure,
)


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
