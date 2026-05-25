"""Tests for run_handlers.create_agent_environment — REDIS_URL gating (MAY-1086)."""

from __future__ import annotations

import pytest

from agentex.lib.cli.handlers.run_handlers import create_agent_environment
from agentex.lib.sdk.config.agent_manifest import AgentManifest


@pytest.fixture
def manifest_path() -> str:
    """A real tutorial manifest with acp_type=async and default redis_enabled."""
    return "examples/tutorials/10_async/00_base/110_pydantic_ai/manifest.yaml"


class TestCreateAgentEnvironmentRedisGating:
    def test_default_seeds_redis_url(self, manifest_path: str, monkeypatch: pytest.MonkeyPatch):
        """With redis_enabled unset (default true), CLI seeds the localhost REDIS_URL."""
        monkeypatch.delenv("REDIS_URL", raising=False)
        manifest = AgentManifest.from_yaml(file_path=manifest_path)
        assert manifest.local_development is not None
        assert manifest.local_development.redis_enabled is True

        env = create_agent_environment(manifest)

        assert env.get("REDIS_URL") == "redis://localhost:6379"

    def test_opt_out_clears_redis_url_when_parent_env_clean(
        self, manifest_path: str, monkeypatch: pytest.MonkeyPatch
    ):
        """With redis_enabled=false and no parent REDIS_URL, REDIS_URL is absent."""
        monkeypatch.delenv("REDIS_URL", raising=False)
        manifest = AgentManifest.from_yaml(file_path=manifest_path)
        assert manifest.local_development is not None
        manifest.local_development.redis_enabled = False

        env = create_agent_environment(manifest)

        assert "REDIS_URL" not in env

    def test_opt_out_clears_redis_url_when_parent_env_has_one(
        self, manifest_path: str, monkeypatch: pytest.MonkeyPatch
    ):
        """With redis_enabled=false, a stale parent-shell REDIS_URL must not leak through."""
        monkeypatch.setenv("REDIS_URL", "redis://leftover.from.parent.shell:6379")
        manifest = AgentManifest.from_yaml(file_path=manifest_path)
        assert manifest.local_development is not None
        manifest.local_development.redis_enabled = False

        env = create_agent_environment(manifest)

        assert "REDIS_URL" not in env
