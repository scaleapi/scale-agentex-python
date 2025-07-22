import typer

from agentex.lib.cli.commands.agents import agents
from agentex.lib.cli.commands.init import init
from agentex.lib.cli.commands.secrets import secrets
from agentex.lib.cli.commands.tasks import tasks
from agentex.lib.cli.commands.uv import uv

# Create the main Typer application
app = typer.Typer(
    context_settings={"help_option_names": ["-h", "--help"], "max_content_width": 800},
    pretty_exceptions_show_locals=False,
    pretty_exceptions_enable=False,
    add_completion=False,
)

# Add the subcommands
app.add_typer(agents, name="agents", help="Get, list, run, build, and deploy agents")
app.add_typer(tasks, name="tasks", help="Get, list, and delete tasks")
app.add_typer(secrets, name="secrets", help="Sync, get, list, and delete secrets")
app.add_typer(
    uv, name="uv", help="Wrapper for uv command with AgentEx-specific enhancements"
)

# Add init command with documentation
app.command(
    help="Initialize a new agent project with a template",
    epilog="Example: agentex init --template temporal my-agent",
)(init)


if __name__ == "__main__":
    app()
