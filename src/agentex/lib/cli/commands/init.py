from enum import Enum
from pathlib import Path
from typing import Any, Dict

import questionary
from jinja2 import Environment, FileSystemLoader
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from agentex.lib.utils.logging import make_logger

logger = make_logger(__name__)
console = Console()

# Get the templates directory relative to this file
TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


class TemplateType(str, Enum):
    TEMPORAL = "temporal"
    DEFAULT = "default"
    SYNC = "sync"


def render_template(
    template_path: str, context: Dict[str, Any], template_type: TemplateType
) -> str:
    """Render a template with the given context"""
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR / template_type.value))
    template = env.get_template(template_path)
    return template.render(**context)


def create_project_structure(
    path: Path, context: Dict[str, Any], template_type: TemplateType, use_uv: bool
):
    """Create the project structure from templates"""
    # Create project directory
    project_dir: Path = path / context["project_name"]
    project_dir.mkdir(parents=True, exist_ok=True)

    # Create project/code directory
    code_dir: Path = project_dir / "project"
    code_dir.mkdir(parents=True, exist_ok=True)

    # Create __init__.py
    (code_dir / "__init__.py").touch()

    # Define project files based on template type
    project_files = {
        TemplateType.TEMPORAL: ["acp.py", "workflow.py", "run_worker.py"],
        TemplateType.DEFAULT: ["acp.py"],
        TemplateType.SYNC: ["acp.py"],
    }[template_type]

    # Create project/code files
    for template in project_files:
        template_path = f"project/{template}.j2"
        output_path = code_dir / template
        output_path.write_text(render_template(template_path, context, template_type))

    # Create root files
    root_templates = {
        ".dockerignore.j2": ".dockerignore",
        "manifest.yaml.j2": "manifest.yaml",
        "README.md.j2": "README.md",
    }

    # Add package management file based on uv choice
    if use_uv:
        root_templates["pyproject.toml.j2"] = "pyproject.toml"
        root_templates["Dockerfile-uv.j2"] = "Dockerfile"
    else:
        root_templates["requirements.txt.j2"] = "requirements.txt"
        root_templates["Dockerfile.j2"] = "Dockerfile"

    # Add development notebook for agents
    root_templates["dev.ipynb.j2"] = "dev.ipynb"

    for template, output in root_templates.items():
        output_path = project_dir / output
        output_path.write_text(render_template(template, context, template_type))

    console.print(f"\n[green]✓[/green] Created project structure at: {project_dir}")


def get_project_context(answers: Dict[str, Any], project_path: Path, manifest_root: Path) -> Dict[str, Any]:
    """Get the project context from user answers"""
    # Use agent_directory_name as project_name
    project_name = answers["agent_directory_name"].replace("-", "_")

    # Now, this is actually the exact same as the project_name because we changed the build root to be ../
    project_path_from_build_root = project_name

    return {
        **answers,
        "project_name": project_name,
        "workflow_class": "".join(
            word.capitalize() for word in answers["agent_name"].split("-")
        )
        + "Workflow",
        "workflow_name": answers["agent_name"],
        "queue_name": project_name + "_queue",
        "project_path_from_build_root": project_path_from_build_root,
    }


def init():
    """Initialize a new agent project"""
    console.print(
        Panel.fit(
            "🤖 [bold blue]Initialize New Agent Project[/bold blue]",
            border_style="blue",
        )
    )

    # Use a Rich table for template descriptions
    table = Table(show_header=True, header_style="bold blue")
    table.add_column("Template", style="cyan", no_wrap=True)
    table.add_column("Description", style="white")
    table.add_row(
        "[bold cyan]Agentic - ACP Only[/bold cyan]",
        "A simple synchronous agent that handles tasks directly. Best for straightforward agents that don't need long-running operations.",
    )
    table.add_row(
        "[bold cyan]Agentic - Temporal[/bold cyan]",
        "An asynchronous agent powered by Temporal workflows. Best for agents that need to handle long-running tasks, retries, or complex state management.",
    )
    table.add_row(
        "[bold cyan]Sync ACP[/bold cyan]",
        "A synchronous agent that handles tasks directly. The difference is that this Sync ACP will be required to respond with the results in the same call as the input.Best for straightforward agents that don't need long-running operations.",
    )
    console.print()
    console.print(table)
    console.print()

    def validate_agent_name(text: str) -> bool | str:
        """Validate agent name follows required format"""
        is_valid = len(text) >= 1 and text.replace("-", "").isalnum() and text.islower()
        if not is_valid:
            return "Invalid name. Use only lowercase letters, numbers, and hyphens. Examples: 'my-agent', 'newsbot'"
        return True

    # Gather project information
    template_type = questionary.select(
        "What type of template would you like to create?",
        choices=[
            {"name": "Agentic - ACP Only", "value": TemplateType.DEFAULT},
            {"name": "Agentic - Temporal", "value": TemplateType.TEMPORAL},
            {"name": "Sync ACP", "value": TemplateType.SYNC},
        ],
    ).ask()
    if not template_type:
        return

    project_path = questionary.path(
        "Where would you like to create your project?", default="."
    ).ask()
    if not project_path:
        return

    agent_name = questionary.text(
        "What's your agent name? (letters, numbers, and hyphens only)",
        validate=validate_agent_name,
    ).ask()
    if not agent_name:
        return

    agent_directory_name = questionary.text(
        "What do you want to name the project folder for your agent?",
        default=agent_name,
    ).ask()
    if not agent_directory_name:
        return

    description = questionary.text(
        "Provide a brief description of your agent:", default="An AgentEx agent"
    ).ask()
    if not description:
        return

    use_uv = questionary.select(
        "Would you like to use uv for package management?",
        choices=[
            {"name": "Yes (Recommended)", "value": True},
            {"name": "No", "value": False},
        ],
    ).ask()

    answers = {
        "template_type": template_type,
        "project_path": project_path,
        "agent_name": agent_name,
        "agent_directory_name": agent_directory_name,
        "description": description,
        "use_uv": use_uv,
    }

    # Derive all names from agent_directory_name and path
    project_path = Path(answers["project_path"]).resolve()
    manifest_root = Path("../../")

    # Get project context
    context = get_project_context(answers, project_path, manifest_root)
    context["template_type"] = answers["template_type"].value
    context["use_uv"] = answers["use_uv"]

    # Create project structure
    create_project_structure(
        project_path, context, answers["template_type"], answers["use_uv"]
    )

    # Show next steps
    console.print("\n[bold green]✨ Project created successfully![/bold green]")
    console.print("\n[bold]Next steps:[/bold]")
    console.print(f"1. cd {project_path}/{context['project_name']}")
    console.print("2. Review and customize the generated files")
    console.print("3. Update the container registry in manifest.yaml")

    if answers["template_type"] == TemplateType.TEMPORAL:
        console.print("4. Run locally:")
        console.print("   agentex agents run --manifest manifest.yaml")
    else:
        console.print("4. Run locally:")
        console.print("   agentex agents run --manifest manifest.yaml")

    console.print("5. Deploy your agent:")
    console.print(
        "   agentex agents deploy --cluster your-cluster --namespace your-namespace"
    )
