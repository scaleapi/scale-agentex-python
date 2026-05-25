"""Tests for run_handlers.create_agent_environment — REDIS_URL gating (MAY-1086)."""

from __future__ import annotations

from pathlib import Path

import pytest

from agentex.lib.cli.handlers.run_handlers import create_agent_environment
from agentex.lib.sdk.config.agent_manifest import AgentManifest

_MANIFEST_TEMPLATE = """\
build:
  context:
    root: .
    dockerfile: Dockerfile

local_development:
  agent:
    port: 8000
    host_address: host.docker.internal
{redis_line}

agent:
  acp_type: async
  name: test-agent
  description: Fixture manifest for run_handlers tests.
"""


def _write_manifest(tmp_path: Path, redis_enabled: bool | None) -> AgentManifest:
    """Write a minimal manifest with the requested redis_enabled value (or omit for default)."""
    redis_line = "" if redis_enabled is None else f"  redis_enabled: {str(redis_enabled).lower()}"
    manifest_path = tmp_path / "manifest.yaml"
    manifest_path.write_text(_MANIFEST_TEMPLATE.format(redis_line=redis_line))
    return AgentManifest.from_yaml(file_path=str(manifest_path))


class TestCreateAgentEnvironmentRedisGating:
    def test_default_seeds_redis_url(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """With redis_enabled unset (default true), CLI seeds the localhost REDIS_URL."""
        monkeypatch.delenv("REDIS_URL", raising=False)
        manifest = _write_manifest(tmp_path, redis_enabled=None)
        assert manifest.local_development is not None
        assert manifest.local_development.redis_enabled is True

        env = create_agent_environment(manifest)

        assert env.get("REDIS_URL") == "redis://localhost:6379"

    def test_opt_out_clears_redis_url_when_parent_env_clean(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """With redis_enabled=false and no parent REDIS_URL, REDIS_URL is absent."""
        monkeypatch.delenv("REDIS_URL", raising=False)
        manifest = _write_manifest(tmp_path, redis_enabled=False)

        env = create_agent_environment(manifest)

        assert "REDIS_URL" not in env

    def test_opt_out_clears_redis_url_when_parent_env_has_one(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """With redis_enabled=false, a stale parent-shell REDIS_URL must not leak through."""
        monkeypatch.setenv("REDIS_URL", "redis://leftover.from.parent.shell:6379")
        manifest = _write_manifest(tmp_path, redis_enabled=False)

        env = create_agent_environment(manifest)

        assert "REDIS_URL" not in env
