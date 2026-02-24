"""Tests for agent_handlers module - prepare_cloud_build_context and package CLI command."""

from __future__ import annotations

import os
import tarfile
import tempfile
from pathlib import Path
from collections.abc import Iterator

import pytest

from agentex.lib.cli.handlers.agent_handlers import (
    CloudBuildContext,
    parse_build_args,
    prepare_cloud_build_context,
)


class TestParseBuildArgs:
    """Tests for parse_build_args helper function."""

    def test_parse_empty_build_args(self):
        """Test parsing None or empty list returns empty dict."""
        assert parse_build_args(None) == {}
        assert parse_build_args([]) == {}

    def test_parse_single_build_arg(self):
        """Test parsing a single KEY=VALUE argument."""
        result = parse_build_args(["FOO=bar"])
        assert result == {"FOO": "bar"}

    def test_parse_multiple_build_args(self):
        """Test parsing multiple KEY=VALUE arguments."""
        result = parse_build_args(["FOO=bar", "BAZ=qux", "NUM=123"])
        assert result == {"FOO": "bar", "BAZ": "qux", "NUM": "123"}

    def test_parse_build_arg_with_equals_in_value(self):
        """Test that values containing '=' are handled correctly."""
        result = parse_build_args(["URL=https://example.com?foo=bar"])
        assert result == {"URL": "https://example.com?foo=bar"}

    def test_parse_invalid_build_arg_ignored(self):
        """Test that invalid format args (no '=') are ignored."""
        result = parse_build_args(["VALID=value", "invalid_no_equals"])
        assert result == {"VALID": "value"}


class TestPrepareCloudBuildContext:
    """Tests for prepare_cloud_build_context function."""

    @pytest.fixture
    def temp_agent_dir(self) -> Iterator[Path]:
        """Create a temporary agent directory with minimal required files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent_dir = Path(tmpdir)

            # Create a minimal Dockerfile
            dockerfile = agent_dir / "Dockerfile"
            dockerfile.write_text("FROM python:3.12-slim\nCMD ['echo', 'hello']")

            # Create a simple Python file to include
            src_dir = agent_dir / "src"
            src_dir.mkdir()
            (src_dir / "main.py").write_text("print('hello')")

            # Create manifest.yaml
            manifest = agent_dir / "manifest.yaml"
            manifest.write_text(
                """
build:
  context:
    root: .
    include_paths:
      - src
    dockerfile: Dockerfile

agent:
  name: test-agent
  acp_type: sync
  description: Test agent
  temporal:
    enabled: false

deployment:
  image:
    repository: test-repo/test-agent
    tag: v1.0.0
"""
            )

            yield agent_dir

    @pytest.fixture
    def temp_agent_dir_no_deployment(self) -> Iterator[Path]:
        """Create a temporary agent directory without deployment config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent_dir = Path(tmpdir)

            dockerfile = agent_dir / "Dockerfile"
            dockerfile.write_text("FROM python:3.12-slim")

            src_dir = agent_dir / "src"
            src_dir.mkdir()
            (src_dir / "main.py").write_text("print('hello')")

            manifest = agent_dir / "manifest.yaml"
            manifest.write_text(
                """
build:
  context:
    root: .
    include_paths:
      - src
    dockerfile: Dockerfile

agent:
  name: test-agent-no-deploy
  acp_type: sync
  description: Test agent without deployment config
  temporal:
    enabled: false
"""
            )

            yield agent_dir

    def test_prepare_cloud_build_context_returns_cloud_build_context(
        self, temp_agent_dir: Path
    ):
        """Test that prepare_cloud_build_context returns a CloudBuildContext."""
        manifest_path = str(temp_agent_dir / "manifest.yaml")

        result = prepare_cloud_build_context(manifest_path=manifest_path)

        assert isinstance(result, CloudBuildContext)
        assert result.agent_name == "test-agent"
        assert result.tag == "v1.0.0"  # From manifest deployment.image.tag
        assert result.image_name == "test-agent"  # Last part of repository
        assert result.dockerfile_path == "Dockerfile"
        assert len(result.archive_bytes) > 0
        assert result.build_context_size_kb > 0

    def test_prepare_cloud_build_context_with_tag_override(self, temp_agent_dir: Path):
        """Test that tag parameter overrides manifest tag."""
        manifest_path = str(temp_agent_dir / "manifest.yaml")

        result = prepare_cloud_build_context(manifest_path=manifest_path, tag="custom-tag")

        assert result.tag == "custom-tag"

    def test_prepare_cloud_build_context_defaults_to_latest_when_no_deployment(
        self, temp_agent_dir_no_deployment: Path
    ):
        """Test that tag defaults to 'latest' when no deployment config exists."""
        manifest_path = str(temp_agent_dir_no_deployment / "manifest.yaml")

        result = prepare_cloud_build_context(manifest_path=manifest_path)

        assert result.tag == "latest"
        assert result.image_name == "<repository>"  # No repository in deployment config

    def test_prepare_cloud_build_context_archive_is_valid_tarball(
        self, temp_agent_dir: Path
    ):
        """Test that the archive bytes are a valid tar.gz file."""
        manifest_path = str(temp_agent_dir / "manifest.yaml")

        result = prepare_cloud_build_context(manifest_path=manifest_path)

        # Write to temp file and verify it's a valid tar.gz
        with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as f:
            f.write(result.archive_bytes)
            temp_tar_path = f.name

        try:
            with tarfile.open(temp_tar_path, "r:gz") as tar:
                names = tar.getnames()
                # Should contain Dockerfile and src/main.py
                assert "Dockerfile" in names
                assert "src/main.py" in names
        finally:
            os.unlink(temp_tar_path)

    def test_prepare_cloud_build_context_missing_dockerfile_raises_error(self):
        """Test that missing Dockerfile raises FileNotFoundError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent_dir = Path(tmpdir)

            # Create manifest pointing to non-existent Dockerfile
            manifest = agent_dir / "manifest.yaml"
            manifest.write_text(
                """
build:
  context:
    root: .
    include_paths: []
    dockerfile: NonExistentDockerfile

agent:
  name: test-agent
  acp_type: sync
  description: Test agent
  temporal:
    enabled: false
"""
            )

            with pytest.raises(FileNotFoundError, match="Dockerfile not found"):
                prepare_cloud_build_context(manifest_path=str(manifest))

    def test_prepare_cloud_build_context_dockerfile_is_directory_raises_error(self):
        """Test that Dockerfile path pointing to directory raises ValueError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent_dir = Path(tmpdir)

            # Create a directory instead of a file for Dockerfile
            dockerfile_dir = agent_dir / "Dockerfile"
            dockerfile_dir.mkdir()

            manifest = agent_dir / "manifest.yaml"
            manifest.write_text(
                """
build:
  context:
    root: .
    include_paths: []
    dockerfile: Dockerfile

agent:
  name: test-agent
  acp_type: sync
  description: Test agent
  temporal:
    enabled: false
"""
            )

            with pytest.raises(ValueError, match="not a file"):
                prepare_cloud_build_context(manifest_path=str(manifest))

    def test_prepare_cloud_build_context_with_build_args(self, temp_agent_dir: Path):
        """Test that build_args are accepted (they're logged but not included in archive)."""
        manifest_path = str(temp_agent_dir / "manifest.yaml")

        # Should not raise - build_args are accepted even though they're just logged
        result = prepare_cloud_build_context(
            manifest_path=manifest_path,
            build_args=["ARG1=value1", "ARG2=value2"],
        )

        assert isinstance(result, CloudBuildContext)
