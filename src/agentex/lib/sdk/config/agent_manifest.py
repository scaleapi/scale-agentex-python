from __future__ import annotations

import io
import shutil
import subprocess
import tarfile
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import IO, Any

from pydantic import Field

from agentex.lib.sdk.config.agent_config import AgentConfig
from agentex.lib.sdk.config.build_config import BuildConfig
from agentex.lib.sdk.config.deployment_config import DeploymentConfig, AuthenticationConfig
from agentex.lib.sdk.config.local_development_config import LocalDevelopmentConfig
from agentex.lib.utils.logging import make_logger
from agentex.lib.utils.model_utils import BaseModel

logger = make_logger(__name__)


class AgentManifest(BaseModel):
    """
    Represents a manifest file that describes how to build and deploy an agent.
    """

    build: BuildConfig
    agent: AgentConfig
    local_development: LocalDevelopmentConfig | None = Field(
        default=None, description="Configuration for local development"
    )
    deployment: DeploymentConfig | None = Field(
        default=None, description="Deployment configuration for the agent"
    )
    auth: AuthenticationConfig | None = Field(default=None, description="Authentication configuration")

    def context_manager(self, build_context_root: Path) -> BuildContextManager:
        """
        Creates a build context manager
        """
        return BuildContextManager(
            agent_manifest=self, build_context_root=build_context_root
        )


class BuildContextManager:
    """
    A gateway used to manage the build context for a docker image
    """

    def __init__(self, agent_manifest: AgentManifest, build_context_root: Path):
        self.agent_manifest = agent_manifest
        self.build_context_root = build_context_root
        self._temp_dir: tempfile.TemporaryDirectory | None = None

        self.path: Path | None = None
        self.dockerfile_path = "Dockerfile"
        self.dockerignore_path = ".dockerignore"
        self.directory_paths: list[Path] = []

    def __enter__(self) -> BuildContextManager:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.path = Path(self._temp_dir.name)

        dockerfile_path = (
            self.build_context_root / self.agent_manifest.build.context.dockerfile
        )
        self.add_dockerfile(root_path=self.path, dockerfile_path=dockerfile_path)

        ignore_patterns = []
        if self.agent_manifest.build.context.dockerignore:
            dockerignore_path = (
                self.build_context_root / self.agent_manifest.build.context.dockerignore
            )
            self.add_dockerignore(
                root_path=self.path, dockerignore_path=dockerignore_path
            )
            ignore_patterns = _extract_dockerignore_patterns(dockerignore_path)

        for directory in self.agent_manifest.build.context.include_paths:
            directory_path = self.build_context_root / directory
            self.add_directory(
                root_path=self.path,
                directory_path=directory_path,
                context_root=self.build_context_root,
                ignore_patterns=ignore_patterns,
            )

        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._temp_dir:
            self._temp_dir.cleanup()

    def add_dockerfile(self, root_path: Path, dockerfile_path: Path) -> None:
        """
        Copies a dockerfile to the temporary context directory root
        """
        shutil.copy2(dockerfile_path, root_path / self.dockerfile_path)

    def add_dockerignore(self, root_path: Path, dockerignore_path: Path) -> None:
        """
        Copies a dockerignore to the temporary context directory root
        """
        shutil.copy2(str(dockerignore_path), root_path / self.dockerignore_path)

    def add_directory(
        self,
        root_path: Path,
        directory_path: Path,
        context_root: Path,
        ignore_patterns: list[str] | None = None,
    ) -> None:
        """
        Copies a directory to the temporary context directory root while maintaining its relative
        path to the context root.
        """
        directory_copy_start_time = time.time()
        last_log_time = directory_copy_start_time

        def copy_function_with_progress(src, dst):
            nonlocal directory_copy_start_time
            nonlocal last_log_time
            logger.info(f"Adding {src} to build context...")
            shutil.copy2(src, dst)
            current_time = time.time()
            time_elapsed = current_time - directory_copy_start_time

            if time_elapsed > 1 and current_time - last_log_time >= 1:
                logger.info(
                    f"Time elapsed copying ({directory_path}): {time_elapsed} "
                    f"seconds"
                )
                last_log_time = current_time
            if time_elapsed > 5:
                logger.warning(
                    f"This may take a while... "
                    f"Consider adding {directory_path} or {src} to your .dockerignore file."
                )

        directory_path_relative_to_root = directory_path.relative_to(context_root)
        all_ignore_patterns = [f"{root_path}*"]
        if ignore_patterns:
            all_ignore_patterns += ignore_patterns
        shutil.copytree(
            src=directory_path,
            dst=root_path / directory_path_relative_to_root,
            ignore=shutil.ignore_patterns(*all_ignore_patterns),
            dirs_exist_ok=True,
            copy_function=copy_function_with_progress,
        )
        self.directory_paths.append(directory_path_relative_to_root)

    @contextmanager
    def zip_stream(self, root_path: Path | None = None) -> Iterator[IO[bytes]]:
        """
        Creates a tar archive of the temporary context directory
        and returns a stream of the archive.
        """
        if not root_path:
            raise ValueError("root_path must be provided")
        context = str(root_path.absolute())
        folders_to_include = "."
        tar_command = ["tar", "-C", context, "-cf", "-"]
        tar_command.extend(folders_to_include)

        logger.info(f"Creating archive: {' '.join(tar_command)}")

        with subprocess.Popen(
            tar_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        ) as proc:
            assert proc.stdout is not None
            try:
                yield proc.stdout
            finally:
                pass

    @staticmethod
    @contextmanager
    def zipped(root_path: Path | None = None) -> Iterator[IO[bytes]]:
        """
        Creates a tar.gz archive of the temporary context directory
        and returns a stream of the archive.
        """
        if not root_path:
            raise ValueError("root_path must be provided")

        tar_buffer = io.BytesIO()

        with tarfile.open(fileobj=tar_buffer, mode="w:gz") as tar_file:
            for path in Path(root_path).rglob(
                "*"
            ):  # Recursively add files to the tar.gz
                if path.is_file():  # Ensure that we're only adding files
                    tar_file.add(path, arcname=path.relative_to(root_path))

        tar_buffer.seek(0)  # Reset the buffer position to the beginning
        yield tar_buffer


def _extract_dockerignore_patterns(dockerignore_path: Path) -> list[str]:
    """
    Extracts glob patterns to ignore from the dockerignore into a list of patterns
    :param dockerignore_path: Path to the dockerignore to extract patterns from
    :return: List of glob patterns to ignore
    :rtype: List[str]
    """
    ignore_patterns = []
    with open(dockerignore_path) as file:
        for line in file:
            ignored_filepath = line.split("#", 1)[0].strip()
            if ignored_filepath:
                ignore_patterns.append(ignored_filepath)
    return ignore_patterns
