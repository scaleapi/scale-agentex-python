import os
import subprocess
import sys

import typer

from agentex.lib.utils.logging import make_logger

logger = make_logger(__name__)


def get_codeartifact_index_url() -> str | None:
    """Get CodeArtifact index URL with authentication token"""
    try:
        # CodeArtifact configuration
        CODEARTIFACT_DOMAIN = "scale"
        CODEARTIFACT_OWNER = "307185671274"
        CODEARTIFACT_REGION = "us-west-2"
        CODEARTIFACT_REPO = "scale-pypi"

        # Fetch the authentication token
        result = subprocess.run(
            [
                "aws",
                "codeartifact",
                "get-authorization-token",
                "--domain",
                CODEARTIFACT_DOMAIN,
                "--domain-owner",
                CODEARTIFACT_OWNER,
                "--region",
                CODEARTIFACT_REGION,
                "--query",
                "authorizationToken",
                "--output",
                "text",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        token = result.stdout.strip()
        if token:
            index_url = f"https://aws:{token}@{CODEARTIFACT_DOMAIN}-{CODEARTIFACT_OWNER}.d.codeartifact.{CODEARTIFACT_REGION}.amazonaws.com/pypi/{CODEARTIFACT_REPO}/simple/"
            logger.info("Successfully obtained CodeArtifact token")
            return index_url
        else:
            logger.warning("Failed to obtain CodeArtifact token")
            return None

    except subprocess.CalledProcessError as e:
        logger.warning(f"Failed to fetch CodeArtifact token: {e}")
        return None
    except FileNotFoundError:
        logger.warning("AWS CLI not found. Install it to use CodeArtifact integration.")
        return None


uv = typer.Typer(
    help="Wrapper for uv command with AgentEx-specific enhancements",
    context_settings={"help_option_names": ["-h", "--help"]},
)

sync_args = typer.Argument(None, help="Additional arguments to pass to uv sync")


@uv.command()
def sync(
    ctx: typer.Context,
    index: str | None = typer.Option(
        None, "--index", "-i", help="UV index URL to use for sync"
    ),
    group: str | None = typer.Option(
        None,
        "--group",
        "-g",
        help="Include dependencies from the specified dependency group",
    ),
    args: list[str] = sync_args,
):
    """Sync dependencies with optional UV_INDEX support"""
    args = args or []

    # Check if help was requested
    if "--help" in args or "-h" in args:
        # Show our custom help instead of passing to uv
        typer.echo(ctx.get_help())
        return

    if index:
        os.environ["UV_INDEX_URL"] = index
        logger.info(f"Using provided UV_INDEX_URL: {index}")
    else:
        # Try to get CodeArtifact index URL if no index provided
        codeartifact_url = get_codeartifact_index_url()
        if codeartifact_url:
            os.environ["UV_INDEX_URL"] = codeartifact_url
            logger.info("Using CodeArtifact UV_INDEX_URL")
        else:
            logger.info("No index URL provided, using default PyPI")

    # Build the uv sync command
    cmd = ["uv", "sync"]

    # Add group if specified
    if group:
        cmd.extend(["--group", group])
        logger.info(f"Using dependency group: {group}")

    # Add any additional arguments
    cmd.extend(args)

    try:
        result = subprocess.run(cmd, check=True)
        sys.exit(result.returncode)
    except subprocess.CalledProcessError as e:
        logger.error(f"uv sync failed with exit code {e.returncode}")
        sys.exit(e.returncode)
    except FileNotFoundError:
        logger.error("uv command not found. Please install uv first.")
        sys.exit(1)


add_args = typer.Argument(None, help="Additional arguments to pass to uv add")


@uv.command()
def add(
    ctx: typer.Context,
    index: str | None = typer.Option(
        None, "--index", "-i", help="UV index URL to use for add"
    ),
    args: list[str] = add_args,
):
    """Add dependencies with optional UV_INDEX support"""

    args = args or []

    # Check if help was requested
    if "--help" in args or "-h" in args:
        # Show our custom help instead of passing to uv
        typer.echo(ctx.get_help())
        return

    if index:
        os.environ["UV_INDEX_URL"] = index
        logger.info(f"Using provided UV_INDEX_URL: {index}")
    else:
        # Try to get CodeArtifact index URL if no index provided
        codeartifact_url = get_codeartifact_index_url()
        if codeartifact_url:
            os.environ["UV_INDEX_URL"] = codeartifact_url
            logger.info("Using CodeArtifact UV_INDEX_URL")
        else:
            logger.info("No index URL provided, using default PyPI")

    # Build the uv add command
    cmd = ["uv", "add"] + (args or [])

    try:
        result = subprocess.run(cmd, check=True)
        sys.exit(result.returncode)
    except subprocess.CalledProcessError as e:
        logger.error(f"uv add failed with exit code {e.returncode}")
        sys.exit(e.returncode)
    except FileNotFoundError:
        logger.error("uv command not found. Please install uv first.")
        sys.exit(1)


run_args = typer.Argument(None, help="Arguments to pass to uv")


@uv.command()
def run(
    ctx: typer.Context,
    args: list[str] = run_args,
):
    """Run any uv command with arguments"""
    if not args:
        # If no arguments provided, show help
        typer.echo(ctx.get_help())
        return

    # Build the uv command
    cmd = ["uv"] + args

    try:
        result = subprocess.run(cmd, check=True)
        sys.exit(result.returncode)
    except subprocess.CalledProcessError as e:
        logger.error(f"uv command failed with exit code {e.returncode}")
        sys.exit(e.returncode)
    except FileNotFoundError:
        logger.error("uv command not found. Please install uv first.")
        sys.exit(1)
