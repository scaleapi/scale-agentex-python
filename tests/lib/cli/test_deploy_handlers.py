"""Tests for the helm values merge_deployment_configs assembles for `agentex agents deploy`."""

from __future__ import annotations

from typing import Any

import pytest

from agentex.config.credentials import CredentialMapping
from agentex.config.agent_config import AgentConfig
from agentex.config.build_config import BuildConfig, BuildContext
from agentex.config.agent_configs import TemporalConfig, TemporalWorkflowConfig
from agentex.config.agent_manifest import AgentManifest
from agentex.config.deployment_config import ImageConfig, DeploymentConfig
from agentex.lib.cli.utils.exceptions import DeploymentError
from agentex.config.environment_config import AgentAuthConfig, AgentEnvironmentConfig
from agentex.lib.cli.handlers.deploy_handlers import InputDeployOverrides, merge_deployment_configs

MANIFEST_TAG = "sha-manifest"


def _manifest(
    env: dict[str, str] | None = None,
    credentials: list[CredentialMapping] | None = None,
    temporal: bool = False,
) -> AgentManifest:
    return AgentManifest(
        build=BuildConfig(context=BuildContext(root=".", dockerfile="Dockerfile", dockerignore=None)),
        agent=AgentConfig(
            name="emu-tax",
            description="Files emu taxes",
            acp_type="async",
            env=env,
            credentials=credentials,
            temporal=(
                TemporalConfig(
                    enabled=True,
                    workflows=[TemporalWorkflowConfig(name="tax-workflow", queue_name="tax-queue")],
                )
                if temporal
                else None
            ),
        ),
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


class TestChartIdentityEnvironment:
    def test_legacy_env_identity_is_moved_to_chart_globals(self):
        manifest = _manifest(
            env={
                "AGENT_NAME": "manifest-agent",
                "WORKFLOW_NAME": "manifest-workflow",
                "WORKFLOW_TASK_QUEUE": "manifest-queue",
                "CUSTOM": "manifest",
            },
            temporal=True,
        )
        env_config = _env_config(
            {
                "global": {
                    "agent": {"name": "global-agent"},
                    "workflow": {"name": "global-workflow", "taskQueue": "global-queue"},
                },
                "env": [
                    {"name": "AGENT_NAME", "value": "staging-agent"},
                    {"name": "WORKFLOW_NAME", "value": "staging-workflow"},
                    {"name": "WORKFLOW_TASK_QUEUE", "value": "staging-queue"},
                    {"name": "CUSTOM", "value": "staging"},
                ],
            }
        )

        values = _merge(manifest, env_config)

        assert values["global"]["agent"]["name"] == "staging-agent"
        assert values["global"]["workflow"] == {
            "name": "staging-workflow",
            "taskQueue": "staging-queue",
        }
        env_by_name = {item["name"]: item["value"] for item in values["env"]}
        assert env_by_name["CUSTOM"] == "staging"
        assert set(env_by_name).isdisjoint({"AGENT_NAME", "WORKFLOW_NAME", "WORKFLOW_TASK_QUEUE"})
        assert values["temporal-worker"]["env"] == values["env"]

    def test_identity_credentials_are_rejected(self):
        credential = CredentialMapping(
            env_var_name="AGENT_NAME",
            secret_name="identity",
            secret_key="agent-name",
        )

        with pytest.raises(DeploymentError, match="AGENT_NAME"):
            _merge(_manifest(credentials=[credential]))

    @pytest.mark.parametrize(
        "helm_overrides",
        [
            {
                "secretEnvVars": [
                    {"name": "AGENT_NAME", "secretName": "identity", "secretKey": "agent-name"}
                ]
            },
            {
                "global": {
                    "secretEnvVars": [
                        {"name": "WORKFLOW_NAME", "secretName": "identity", "secretKey": "workflow-name"}
                    ]
                }
            },
            {
                "temporal-worker": {
                    "secretEnvVars": [
                        {
                            "name": "WORKFLOW_TASK_QUEUE",
                            "secretName": "identity",
                            "secretKey": "task-queue",
                        }
                    ]
                }
            },
        ],
    )
    def test_identity_secret_helm_overrides_are_rejected(self, helm_overrides: dict[str, Any]):
        with pytest.raises(DeploymentError, match="Chart-owned identity variables"):
            _merge(_manifest(temporal=True), _env_config(helm_overrides))

    @pytest.mark.parametrize("path", ["global", "temporal-worker"])
    def test_identity_container_specific_env_is_rejected(self, path: str):
        with pytest.raises(DeploymentError, match="Configure them under helm_overrides.global"):
            _merge(
                _manifest(temporal=True),
                _env_config({path: {"env": [{"name": "WORKFLOW_NAME", "value": "legacy"}]}}),
            )

    @pytest.mark.parametrize("group_name", ["agent", "workflow"])
    def test_identity_global_groups_must_be_mappings(self, group_name: str):
        with pytest.raises(
            DeploymentError,
            match=rf"helm_overrides\.global\.{group_name} must be a mapping",
        ):
            _merge(
                _manifest(temporal=True),
                _env_config({"global": {group_name: "invalid"}}),
            )
