from __future__ import annotations

from enum import Enum
from typing import Any, Dict
from pathlib import Path

import questionary
from jinja2 import Environment, FileSystemLoader
from rich.rule import Rule
from rich.text import Text
from rich.panel import Panel
from rich.table import Table
from rich.console import Console

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
        "environments.yaml.j2": "environments.yaml",
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


def get_project_context(answers: Dict[str, Any], project_path: Path, manifest_root: Path) -> Dict[str, Any]:  # noqa: ARG001
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
        "Provide a brief description of your agent:", default="An Agentex agent"
    ).ask()
    if not description:
        return
    
    agent_input_type = questionary.select(
        "What type of input will your agent handle?",
        choices=[
            {"name": "Text Input", "value": "text"},
            {"name": "Structured Input", "value": "json"},
        ],    
    ).ask()
    if not agent_input_type:
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
        "agent_input_type": agent_input_type,
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

    # Show success message
    console.print()
    success_text = Text("✅ Project created successfully!", style="bold green")
    success_panel = Panel(
        success_text,
        border_style="green",
        padding=(0, 2),
        title="[bold white]Status[/bold white]",
        title_align="left"
    )
    console.print(success_panel)
    
    # Main header
    console.print()
    console.print(Rule("[bold blue]Next Steps[/bold blue]", style="blue"))
    console.print()

    # Local Development Section
    local_steps = Text()
    local_steps.append("1. ", style="bold white")
    local_steps.append("Navigate to your project directory:\n", style="white")
    local_steps.append(f"   cd {project_path}/{context['project_name']}\n\n", style="dim cyan")
    
    local_steps.append("2. ", style="bold white")
    local_steps.append("Review the generated files. ", style="white")
    local_steps.append("project/acp.py", style="yellow")
    local_steps.append(" is your agent's entrypoint.\n", style="white")
    local_steps.append("   See ", style="dim white")
    local_steps.append("https://agentex.sgp.scale.com/docs", style="blue underline")
    local_steps.append(" for how to customize different agent types", style="dim white")
    local_steps.append("\n\n", style="white")
    
    local_steps.append("3. ", style="bold white")
    local_steps.append("Set up your environment and test locally ", style="white")
    local_steps.append("(no deployment needed)", style="dim white")
    local_steps.append(":\n", style="white")
    local_steps.append("   uv venv && uv sync && source .venv/bin/activate", style="dim cyan")
    local_steps.append("\n   agentex agents run --manifest manifest.yaml", style="dim cyan")
    
    local_panel = Panel(
        local_steps,
        title="[bold blue]Development Setup[/bold blue]",
        title_align="left",
        border_style="blue",
        padding=(1, 2)
    )
    console.print(local_panel)
    console.print()

    # Prerequisites Note
    prereq_text = Text()
    prereq_text.append("The above is all you need for local development. Once you're ready for production, read this box and below.\n\n", style="white")
    
    prereq_text.append("• ", style="bold white")
    prereq_text.append("Prerequisites for Production: ", style="bold yellow")
    prereq_text.append("You need Agentex hosted on a Kubernetes cluster.\n", style="white")
    prereq_text.append("  See ", style="dim white")
    prereq_text.append("https://agentex.sgp.scale.com/docs", style="blue underline")
    prereq_text.append(" for setup instructions. ", style="dim white")
    prereq_text.append("Scale GenAI Platform (SGP) customers", style="dim cyan")
    prereq_text.append(" already have this setup as part of their enterprise license.\n\n", style="dim white")
    
    prereq_text.append("• ", style="bold white")
    prereq_text.append("Best Practice: ", style="bold blue")
    prereq_text.append("Use CI/CD pipelines for production deployments, not manual commands.\n", style="white")
    prereq_text.append("  Commands below demonstrate Agentex's quick deployment capabilities.", style="dim white")
    
    prereq_panel = Panel(
        prereq_text,
        border_style="yellow",
        padding=(1, 2)
    )
    console.print(prereq_panel)
    console.print()

    # Production Setup Section (includes deployment)
    prod_steps = Text()
    prod_steps.append("4. ", style="bold white")
    prod_steps.append("Configure where to push your container image", style="white")
    prod_steps.append(":\n", style="white")
    prod_steps.append("   Edit ", style="dim white")
    prod_steps.append("manifest.yaml", style="dim yellow")
    prod_steps.append(" → ", style="dim white")
    prod_steps.append("deployment.image.repository", style="dim yellow")
    prod_steps.append(" → replace ", style="dim white")
    prod_steps.append('""', style="dim red")
    prod_steps.append(" with your registry", style="dim white")
    prod_steps.append("\n   Examples: ", style="dim white")
    prod_steps.append("123456789012.dkr.ecr.us-west-2.amazonaws.com/my-agent", style="dim blue")
    prod_steps.append(", ", style="dim white")
    prod_steps.append("gcr.io/my-project", style="dim blue")
    prod_steps.append(", ", style="dim white")
    prod_steps.append("myregistry.azurecr.io", style="dim blue")
    prod_steps.append("\n\n", style="white")
    
    prod_steps.append("5. ", style="bold white")
    prod_steps.append("Build your agent as a container and push to registry", style="white")
    prod_steps.append(":\n", style="white")
    prod_steps.append("   agentex agents build --manifest manifest.yaml --registry <your-registry> --push", style="dim cyan")
    prod_steps.append("\n\n", style="white")
    
    prod_steps.append("6. ", style="bold white")
    prod_steps.append("Upload secrets to cluster ", style="white")
    prod_steps.append("(API keys, credentials your agent needs)", style="dim white")
    prod_steps.append(":\n", style="white")
    prod_steps.append("   agentex secrets sync --manifest manifest.yaml --cluster your-cluster", style="dim cyan")
    prod_steps.append("\n   ", style="white")
    prod_steps.append("Note: ", style="dim yellow")
    prod_steps.append("Secrets are ", style="dim white")
    prod_steps.append("never stored in manifest.yaml", style="dim red")
    prod_steps.append(". You provide them via ", style="dim white")
    prod_steps.append("--values file", style="dim blue")
    prod_steps.append(" or interactive prompts", style="dim white")
    prod_steps.append("\n\n", style="white")
    
    prod_steps.append("7. ", style="bold white")
    prod_steps.append("Deploy your agent to run on the cluster", style="white")
    prod_steps.append(":\n", style="white")
    prod_steps.append("   agentex agents deploy --cluster your-cluster --namespace your-namespace", style="dim cyan")
    prod_steps.append("\n\n", style="white")
    prod_steps.append("Note: These commands use Helm charts hosted by Scale to deploy agents.", style="dim italic")
    
    prod_panel = Panel(
        prod_steps,
        title="[bold magenta]Production Setup & Deployment[/bold magenta]",
        title_align="left",
        border_style="magenta",
        padding=(1, 2)
    )
    console.print(prod_panel)
    
    # Professional footer with helpful context
    console.print()
    console.print(Rule(style="dim white"))
    
    # Add helpful context about the workflow
    help_text = Text()
    help_text.append("ℹ️  ", style="blue")
    help_text.append("Quick Start: ", style="bold white")
    help_text.append("Steps 1-3 for local development. Steps 4-7 require Agentex cluster for production.", style="dim white")
    console.print("   ", help_text)
    
    tip_text = Text()
    tip_text.append("💡 ", style="yellow")
    tip_text.append("Need help? ", style="bold white")
    tip_text.append("Use ", style="dim white")
    tip_text.append("agentex --help", style="cyan")
    tip_text.append(" or ", style="dim white")
    tip_text.append("agentex [command] --help", style="cyan")
    tip_text.append(" for detailed options", style="dim white")
    console.print("   ", tip_text)
    console.print()
