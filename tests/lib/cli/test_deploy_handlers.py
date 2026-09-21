"""Tests for the helm values merge_deployment_configs assembles for `agentex agents deploy`."""

from __future__ import annotations

from typing import Any

from agentex.config.agent_config import AgentConfig
from agentex.config.build_config import BuildConfig, BuildContext
from agentex.config.agent_manifest import AgentManifest
from agentex.config.deployment_config import ImageConfig, DeploymentConfig
from agentex.config.environment_config import AgentAuthConfig, AgentEnvironmentConfig
from agentex.lib.cli.handlers.deploy_handlers import InputDeployOverrides, merge_deployment_configs

MANIFEST_TAG = "sha-manifest"


def _manifest(env: dict[str, str] | None = None) -> AgentManifest:
    return AgentManifest(
        build=BuildConfig(context=BuildContext(root=".", dockerfile="Dockerfile", dockerignore=None)),
        agent=AgentConfig(name="emu-tax", description="Files emu taxes", acp_type="async", env=env),
        deployment=DeploymentConfig(image=ImageConfig(repository="registry.example.com/emu-tax", tag=MANIFEST_TAG)),
    )


def _env_config(helm_overrides: dict[str, Any]) -> AgentEnvironmentConfig:
    return AgentEnvironmentConfig(auth=AgentAuthConfig(principal={"user_id": "u-1"}), helm_overrides=helm_overrides)


def _merge(
    manifest: AgentManifest,
    env_config: AgentEnvironmentConfig | None = None,
    image_tag: str | None = None,
) -> dict[str, Any]:
    overrides = InputDeployOverrides(image_tag=image_tag)
    return merge_deployment_configs(manifest, env_config, overrides, "/nonexistent/manifest.yaml")


class TestAgentVersion:
    def test_stamped_from_the_deploy_image_tag(self):
        values = _merge(_manifest(), image_tag="sha-cli")

        assert values["global"]["agent"]["version"] == "sha-cli"

    def test_follows_an_image_tag_overridden_in_helm_overrides(self):
        values = _merge(_manifest(), _env_config({"global": {"image": {"tag": "sha-env"}}}))

        assert values["global"]["image"]["tag"] == "sha-env"
        assert values["global"]["agent"]["version"] == "sha-env"

    def test_explicit_helm_override_of_the_version_wins(self):
        values = _merge(_manifest(), _env_config({"global": {"agent": {"version": "pinned"}}}))

        assert values["global"]["agent"]["version"] == "pinned"

    def test_skipped_when_the_manifest_env_declares_agent_version(self):
        values = _merge(_manifest(env={"AGENT_VERSION": "v1.2.3"}))

        assert "version" not in values["global"]["agent"]
        assert {"name": "AGENT_VERSION", "value": "v1.2.3"} in values["env"]

    def test_skipped_when_the_environment_env_declares_agent_version(self):
        values = _merge(_manifest(), _env_config({"env": [{"name": "AGENT_VERSION", "value": "v9"}]}))

        assert "version" not in values["global"]["agent"]
