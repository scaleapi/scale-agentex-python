from __future__ import annotations

from typing import NamedTuple
from pathlib import Path

from rich.console import Console
from python_on_whales import DockerException, docker

from agentex.lib.cli.debug import DebugConfig
from agentex.lib.utils.logging import make_logger
from agentex.lib.cli.handlers.run_handlers import RunError, run_agent as _run_agent
from agentex.lib.sdk.config.agent_manifest import AgentManifest, BuildContextManager

logger = make_logger(__name__)
console = Console()


class DockerBuildError(Exception):
    """An error occurred during docker build"""


class CloudBuildContext(NamedTuple):
    """Contains the prepared build context for cloud builds."""

    archive_bytes: bytes
    dockerfile_path: str
    agent_name: str
    tag: str
    image_name: str
    build_context_size_kb: float


def build_agent(
    manifest_path: str,
    registry_url: str,
    repository_name: str | None,
    platforms: list[str],
    push: bool = False,
    secret: str | None = None,
    tag: str | None = None,
    build_args: list[str] | None = None,
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
    build_context_root = (Path(manifest_path).parent / agent_manifest.build.context.root).resolve()

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
            f"Dockerfile path: {build_context.path / build_context.dockerfile_path}"  # type: ignore[operator]
        )

        try:
            # Prepare build arguments
            docker_build_kwargs = {
                "context_path": str(build_context.path),
                "file": str(build_context.path / build_context.dockerfile_path),  # type: ignore[operator]
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
                        logger.warning(f"Invalid build arg format: {arg}. Expected KEY=VALUE")

                if docker_build_args:
                    docker_build_kwargs["build_args"] = docker_build_args
                    logger.info(f"Using build args: {list(docker_build_args.keys())}")

            # Add secret if provided
            if secret:
                docker_build_kwargs["secrets"] = [secret]

            if push:
                # Build and push in one step for multi-platform builds
                logger.info("Building and pushing image...")
                docker_build_kwargs["push"] = True  # Push directly after build for multi-platform
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
    import sys
    import signal
    import asyncio

    # Flag to track if we're shutting down
    shutting_down = False

    def signal_handler(signum, _frame):
        """Handle signals by raising KeyboardInterrupt"""
        nonlocal shutting_down
        if shutting_down:
            # If we're already shutting down and get another signal, force exit
            logger.info(f"Force exit on signal {signum}")
            sys.exit(1)

        shutting_down = True
        logger.info(f"Received signal {signum}, shutting down...")
        raise KeyboardInterrupt()

    # Set up signal handling for the main thread
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        asyncio.run(_run_agent(manifest_path, debug_config))
    except KeyboardInterrupt:
        logger.info("Shutdown completed.")
        sys.exit(0)
    except RunError as e:
        raise RuntimeError(str(e)) from e


def parse_build_args(build_args: list[str] | None) -> dict[str, str]:
    """Parse build arguments from KEY=VALUE format to a dictionary.

    Args:
        build_args: List of build arguments in KEY=VALUE format

    Returns:
        Dictionary mapping keys to values
    """
    result: dict[str, str] = {}
    if not build_args:
        return result

    for arg in build_args:
        if "=" in arg:
            key, value = arg.split("=", 1)
            result[key] = value
        else:
            logger.warning(f"Invalid build arg format: {arg}. Expected KEY=VALUE")

    return result


def prepare_cloud_build_context(
    manifest_path: str,
    tag: str | None = None,
    build_args: list[str] | None = None,
) -> CloudBuildContext:
    """Prepare the build context for cloud-based container builds.

    Reads the manifest, prepares the build context by copying files according to
    the include_paths and dockerignore, then creates a compressed tar.gz archive
    ready for upload to a cloud build service.

    Args:
        manifest_path: Path to the agent manifest file
        tag: Image tag override (if None, reads from manifest's deployment.image.tag)
        build_args: List of build arguments in KEY=VALUE format

    Returns:
        CloudBuildContext containing the archive bytes, dockerfile path, and metadata
    """
    agent_manifest = AgentManifest.from_yaml(file_path=manifest_path)
    build_context_root = (Path(manifest_path).parent / agent_manifest.build.context.root).resolve()

    agent_name = agent_manifest.agent.name
    dockerfile_path = agent_manifest.build.context.dockerfile

    # Validate that the Dockerfile exists
    full_dockerfile_path = build_context_root / dockerfile_path
    if not full_dockerfile_path.exists():
        raise FileNotFoundError(
            f"Dockerfile not found at: {full_dockerfile_path}\n"
            f"Check that 'build.context.dockerfile' in your manifest points to an existing file."
        )
    if not full_dockerfile_path.is_file():
        raise ValueError(
            f"Dockerfile path is not a file: {full_dockerfile_path}\n"
            f"'build.context.dockerfile' must point to a file, not a directory."
        )

    # Get tag and repository from manifest if not provided
    if tag is None:
        if agent_manifest.deployment and agent_manifest.deployment.image:
            tag = agent_manifest.deployment.image.tag
        else:
            tag = "latest"

    # Get repository name from manifest (just the repo name, not the full registry URL)
    if agent_manifest.deployment and agent_manifest.deployment.image:
        repository = agent_manifest.deployment.image.repository
        if repository:
            # Extract just the repo name (last part after any slashes)
            image_name = repository.split("/")[-1]
        else:
            image_name = "<repository>"
    else:
        image_name = "<repository>"

    logger.info(f"Agent: {agent_name}")
    logger.info(f"Image name: {image_name}")
    logger.info(f"Build context root: {build_context_root}")
    logger.info(f"Dockerfile: {dockerfile_path}")
    logger.info(f"Tag: {tag}")

    if agent_manifest.build.context.include_paths:
        logger.info(f"Include paths: {agent_manifest.build.context.include_paths}")

    parsed_build_args = parse_build_args(build_args)
    if parsed_build_args:
        logger.info(f"Build args: {list(parsed_build_args.keys())}")

    logger.info("Preparing build context...")

    with agent_manifest.context_manager(build_context_root) as build_context:
        # Compress the prepared context using the static zipped method
        with BuildContextManager.zipped(root_path=build_context.path) as archive_buffer:
            archive_bytes = archive_buffer.read()

        build_context_size_kb = len(archive_bytes) / 1024
        logger.info(f"Build context size: {build_context_size_kb:.1f} KB")

        return CloudBuildContext(
            archive_bytes=archive_bytes,
            dockerfile_path=build_context.dockerfile_path,
            agent_name=agent_name,
            tag=tag,
            image_name=image_name,
            build_context_size_kb=build_context_size_kb,
        )
