"""Tests for the slim-safe helm-values generation in ``agentex.config.helm_values``.

These pin the values contract for the ``agentex-agent`` chart so consumers (the
CLI's ``deploy_handlers`` and server-side deployers) can rely on a single
implementation. See AGX1-357 for the promotion plan.
"""

from __future__ import annotations

import json
import base64

import pytest

from agentex.config.helm_values import (
    TEMPORAL_WORKER_KEY,
    AUTH_PRINCIPAL_ENV_VAR,
    build_acp_command,
    derive_acp_module,
    encode_principal_context,
    merge_deployment_configs,
    convert_env_vars_dict_to_list,
)
from agentex.config.agent_config import AgentConfig
from agentex.config.build_config import BuildConfig, BuildContext
from agentex.config.agent_configs import TemporalConfig, TemporalWorkflowConfig
from agentex.config.agent_manifest import AgentManifest
from agentex.config.deployment_config import (
    ImageConfig,
    ResourceConfig,
    DeploymentConfig,
    ResourceRequirements,
    ImagePullSecretConfig,
)
from agentex.config.environment_config import AgentAuthConfig, AgentEnvironmentConfig
from agentex.config.local_development_config import LocalAgentConfig, LocalPathsConfig, LocalDevelopmentConfig

BUILD = BuildConfig(context=BuildContext(root=".", dockerfile="Dockerfile"))


def make_manifest(**kwargs) -> AgentManifest:
    defaults = dict(
        build=BUILD,
        agent=AgentConfig(name="test-agent", acp_type="sync", description="test"),
        deployment=DeploymentConfig(image=ImageConfig(repository="manifest-repo", tag="manifest-tag")),
    )
    defaults.update(kwargs)
    return AgentManifest(**defaults)


def make_env_config(**kwargs) -> AgentEnvironmentConfig:
    defaults = dict(auth=AgentAuthConfig(principal={"user_id": "u1", "account_id": "a1"}))
    defaults.update(kwargs)
    return AgentEnvironmentConfig(**defaults)


def merge(manifest: AgentManifest, env_config: AgentEnvironmentConfig | None = None, **kwargs):
    kwargs.setdefault("repository", "repo.example.com/agent")
    kwargs.setdefault("image_tag", "abc123")
    return merge_deployment_configs(manifest, env_config, **kwargs)


class TestMergeDeploymentConfigs:
    def test_basic_merge_produces_chart_contract(self) -> None:
        helm_values = merge(make_manifest())

        assert helm_values["global"]["image"] == {
            "repository": "repo.example.com/agent",
            "tag": "abc123",
            "pullPolicy": "IfNotPresent",
        }
        assert helm_values["global"]["agent"] == {
            "name": "test-agent",
            "description": "test",
            "acp_type": "sync",
        }
        assert helm_values["replicaCount"] == 1
        assert helm_values["resources"]["requests"] == {"cpu": "500m", "memory": "1Gi"}
        assert helm_values["autoscaling"] == {
            "enabled": True,
            "minReplicas": 1,
            "maxReplicas": 10,
            "targetCPUUtilizationPercentage": 50,
        }
        # No temporal config -> no temporal-worker block
        assert TEMPORAL_WORKER_KEY not in helm_values

    def test_missing_deployment_raises(self) -> None:
        manifest = make_manifest(deployment=None)
        with pytest.raises(ValueError, match="No deployment configuration"):
            merge(manifest)

    @pytest.mark.parametrize("field", ["repository", "image_tag"])
    def test_empty_image_inputs_raise(self, field: str) -> None:
        with pytest.raises(ValueError, match="Repository and image tag are required"):
            merge(make_manifest(), **{field: ""})

    def test_default_command_derived_from_manifest(self) -> None:
        helm_values = merge(make_manifest())
        assert helm_values["command"] == ["uvicorn", "project.acp:acp", "--host", "0.0.0.0", "--port", "8000"]

    def test_explicit_acp_module_wins(self) -> None:
        helm_values = merge(make_manifest(), acp_module="custom.entrypoint")
        assert helm_values["command"][1] == "custom.entrypoint:acp"

    def test_command_in_helm_overrides_suppresses_injection(self) -> None:
        env_config = make_env_config(helm_overrides={"command": ["python", "-m", "custom"]})
        helm_values = merge(make_manifest(), env_config)
        assert helm_values["command"] == ["python", "-m", "custom"]

    def test_temporal_agent_gets_worker_block_and_workflow(self) -> None:
        manifest = make_manifest(
            agent=AgentConfig(
                name="t-agent",
                acp_type="async",
                description="t",
                temporal=TemporalConfig(
                    enabled=True,
                    workflows=[TemporalWorkflowConfig(name="wf", queue_name="q")],
                ),
            )
        )
        helm_values = merge(manifest)
        assert helm_values[TEMPORAL_WORKER_KEY]["enabled"] is True
        assert helm_values["global"]["workflow"] == {"name": "wf", "taskQueue": "q"}

    def test_env_precedence_manifest_then_overrides_then_secrets(self) -> None:
        manifest = make_manifest(
            agent=AgentConfig(
                name="e-agent",
                acp_type="sync",
                description="e",
                env={"A": "manifest", "B": "manifest", "C": "manifest"},
                credentials=[{"env_var_name": "C", "secret_name": "s", "secret_key": "k"}],
            )
        )
        env_config = make_env_config(helm_overrides={"env": [{"name": "B", "value": "override"}]})
        helm_values = merge(manifest, env_config)

        env_by_name = {e["name"]: e["value"] for e in helm_values["env"]}
        assert env_by_name["A"] == "manifest"
        assert env_by_name["B"] == "override"
        # C moved to secretEnvVars; the secret wins over the plain env var
        assert "C" not in env_by_name
        assert helm_values["secretEnvVars"] == [{"name": "C", "secretName": "s", "secretKey": "k"}]

    def test_temporal_worker_inherits_env_and_secrets(self) -> None:
        manifest = make_manifest(
            agent=AgentConfig(
                name="t-agent",
                acp_type="async",
                description="t",
                env={"A": "v"},
                credentials=[{"env_var_name": "S", "secret_name": "s", "secret_key": "k"}],
                temporal=TemporalConfig(
                    enabled=True,
                    workflows=[TemporalWorkflowConfig(name="wf", queue_name="q")],
                ),
            )
        )
        helm_values = merge(manifest, make_env_config())
        worker = helm_values[TEMPORAL_WORKER_KEY]
        assert {e["name"] for e in worker["env"]} == {"A", AUTH_PRINCIPAL_ENV_VAR}
        assert worker["secretEnvVars"] == [{"name": "S", "secretName": "s", "secretKey": "k"}]

    def test_auth_principal_encoded_into_env(self) -> None:
        helm_values = merge(make_manifest(), make_env_config())
        env_by_name = {e["name"]: e["value"] for e in helm_values["env"]}
        decoded = json.loads(base64.b64decode(env_by_name[AUTH_PRINCIPAL_ENV_VAR]))
        assert decoded == {"user_id": "u1", "account_id": "a1"}

    def test_empty_auth_principal_raises(self) -> None:
        env_config = make_env_config(auth=AgentAuthConfig(principal={}))
        with pytest.raises(ValueError, match="Auth principal unable to be encoded"):
            merge(make_manifest(), env_config)

    def test_image_pull_secrets_copied_from_manifest(self) -> None:
        manifest = make_manifest(
            deployment=DeploymentConfig(
                image=ImageConfig(repository="r", tag="t"),
                imagePullSecrets=[ImagePullSecretConfig(name="regcred")],
            )
        )
        helm_values = merge(manifest)
        assert helm_values["imagePullSecrets"] == [{"name": "regcred"}]
        assert helm_values["global"]["imagePullSecrets"] == [{"name": "regcred"}]

    def test_helm_overrides_deep_merge(self) -> None:
        env_config = make_env_config(helm_overrides={"resources": {"limits": {"cpu": "2"}}, "extraKey": {"a": 1}})
        helm_values = merge(make_manifest(), env_config)
        # Override applied without clobbering sibling keys
        assert helm_values["resources"]["limits"]["cpu"] == "2"
        assert helm_values["resources"]["limits"]["memory"] == "1Gi"
        assert helm_values["resources"]["requests"] == {"cpu": "500m", "memory": "1Gi"}
        assert helm_values["extraKey"] == {"a": 1}

    def test_resources_from_manifest(self) -> None:
        manifest = make_manifest(
            deployment=DeploymentConfig(
                image=ImageConfig(repository="r", tag="t"),
                **{
                    "global": {
                        "replicaCount": 3,
                        "resources": ResourceConfig(
                            requests=ResourceRequirements(cpu="1", memory="2Gi"),
                            limits=ResourceRequirements(cpu="4", memory="8Gi"),
                        ),
                    }
                },
            )
        )
        helm_values = merge(manifest)
        assert helm_values["replicaCount"] == 3
        assert helm_values["resources"] == {
            "requests": {"cpu": "1", "memory": "2Gi"},
            "limits": {"cpu": "4", "memory": "8Gi"},
        }


class TestDeriveAcpModule:
    def test_default_when_no_local_development(self) -> None:
        assert derive_acp_module(make_manifest()) == "project.acp"

    def test_derived_from_configured_path(self) -> None:
        manifest = make_manifest(
            local_development=LocalDevelopmentConfig(
                agent=LocalAgentConfig(port=5000),
                paths=LocalPathsConfig(acp="src/agents/main.py"),
            )
        )
        assert derive_acp_module(manifest) == "src.agents.main"


class TestSmallHelpers:
    def test_build_acp_command(self) -> None:
        assert build_acp_command("project.acp") == [
            "uvicorn",
            "project.acp:acp",
            "--host",
            "0.0.0.0",
            "--port",
            "8000",
        ]

    def test_convert_env_vars_dict_to_list(self) -> None:
        assert convert_env_vars_dict_to_list({"A": "1"}) == [{"name": "A", "value": "1"}]

    def test_encode_principal_context_none_cases(self) -> None:
        assert encode_principal_context(None) is None
        assert encode_principal_context(AgentAuthConfig(principal={})) is None
