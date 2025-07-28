from __future__ import annotations

from pathlib import Path

from python_on_whales import DockerException, docker
from rich.console import Console

from agentex.lib.cli.handlers.run_handlers import RunError
from agentex.lib.cli.handlers.run_handlers import run_agent as _run_agent
from agentex.lib.cli.debug import DebugConfig
from agentex.lib.sdk.config.agent_manifest import AgentManifest
from agentex.lib.utils.logging import make_logger

logger = make_logger(__name__)
console = Console()


class DockerBuildError(Exception):
    """An error occurred during docker build"""


def build_agent(
    manifest_path: str,
    registry_url: str,
    repository_name: str | None,
    platforms: list[str],
    push: bool = False,
    secret: str = None,
    tag: str = None,
    build_args: list[str] = None,
) -> str:
    """Build the agent locally and optionally push to registry

    Args:
        manifest_path: Path to the agent manifest file
        registry_url: Registry URL for pushing the image
        push: Whether to push the image to the registry
        secret: Docker build secret in format 'id=secret-id,src=path-to-secret-file'
        tag: Image tag to use (defaults to 'latest')
        build_args: List of Docker build arguments in format 'KEY=VALUE'

    Returns:
        The image URL
    """
    agent_manifest = AgentManifest.from_yaml(file_path=manifest_path)
    build_context_root = (
        Path(manifest_path).parent / agent_manifest.build.context.root
    ).resolve()

    repository_name = repository_name or agent_manifest.agent.name

    # Prepare image name
    if registry_url:
        image_name = f"{registry_url}/{repository_name}"
    else:
        image_name = repository_name

    if tag:
        image_name = f"{image_name}:{tag}"
    else:
        image_name = f"{image_name}:latest"

    with agent_manifest.context_manager(build_context_root) as build_context:
        logger.info(f"Building image {image_name} locally...")

        # Log build context information for debugging
        logger.info(f"Build context path: {build_context.path}")
        logger.info(
            f"Dockerfile path: {build_context.path / build_context.dockerfile_path}"
        )

        try:
            # Prepare build arguments
            docker_build_kwargs = {
                "context_path": str(build_context.path),
                "file": str(build_context.path / build_context.dockerfile_path),
                "tags": [image_name],
                "platforms": platforms,
            }

            # Add Docker build args if provided
            if build_args:
                docker_build_args = {}
                for arg in build_args:
                    if "=" in arg:
                        key, value = arg.split("=", 1)
                        docker_build_args[key] = value
                    else:
                        logger.warning(
                            f"Invalid build arg format: {arg}. Expected KEY=VALUE"
                        )

                if docker_build_args:
                    docker_build_kwargs["build_args"] = docker_build_args
                    logger.info(f"Using build args: {list(docker_build_args.keys())}")

            # Add secret if provided
            if secret:
                docker_build_kwargs["secrets"] = [secret]

            if push:
                # Build and push in one step for multi-platform builds
                logger.info("Building and pushing image...")
                docker_build_kwargs["push"] = (
                    True  # Push directly after build for multi-platform
                )
                docker.buildx.build(**docker_build_kwargs)

                logger.info(f"Successfully built and pushed {image_name}")
            else:
                # Build only
                logger.info("Building image...")
                docker.buildx.build(**docker_build_kwargs)

                logger.info(f"Successfully built {image_name}")

        except DockerException as error:
            error_msg = error.stderr if error.stderr else str(error)
            action = "build or push" if push else "build"
            logger.error(f"{action.capitalize()} failed: {error_msg}", exc_info=True)
            raise DockerBuildError(
                f"Docker {action} failed: {error_msg}\n"
                f"Build context: {build_context.path}\n"
                f"Dockerfile path: {build_context.dockerfile_path}"
            ) from error

    return image_name


def run_agent(manifest_path: str, debug_config: "DebugConfig | None" = None):
    """Run an agent locally from the given manifest"""
    import asyncio
    import signal
    import sys

    # Flag to track if we're shutting down
    shutting_down = False

    def signal_handler(signum, frame):
        """Handle signals by raising KeyboardInterrupt"""
        nonlocal shutting_down
        if shutting_down:
            # If we're already shutting down and get another signal, force exit
            print(f"\nForce exit on signal {signum}")
            sys.exit(1)
        
        shutting_down = True
        print(f"\nReceived signal {signum}, shutting down...")
        raise KeyboardInterrupt()
    
    # Set up signal handling for the main thread
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        asyncio.run(_run_agent(manifest_path, debug_config))
    except KeyboardInterrupt:
        print("Shutdown completed.")
        sys.exit(0)
    except RunError as e:
        raise RuntimeError(str(e)) from e
