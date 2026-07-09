"""Tests for the CLI wrapper around ``agentex.config.helm_values``.

The wrapper keeps the historical ``deploy_handlers`` signature and
``DeploymentError`` contract while delegating the pure mapping to the slim
module; these tests pin that delegation.
"""

from __future__ import annotations

import pytest

from agentex.lib.cli.handlers import deploy_handlers
from agentex.config.helm_values import merge_deployment_configs as merge_helm_values
from agentex.config.agent_config import AgentConfig
from agentex.config.build_config import BuildConfig, BuildContext
from agentex.config.agent_manifest import AgentManifest
from agentex.config.deployment_config import ImageConfig, DeploymentConfig
from agentex.lib.cli.utils.exceptions import DeploymentError
from agentex.config.environment_config import AgentAuthConfig, AgentEnvironmentConfig
from agentex.lib.cli.handlers.deploy_handlers import InputDeployOverrides, merge_deployment_configs


def make_manifest(**kwargs) -> AgentManifest:
    defaults = dict(
        build=BuildConfig(context=BuildContext(root=".", dockerfile="Dockerfile")),
        agent=AgentConfig(name="test-agent", acp_type="sync", description="test"),
        deployment=DeploymentConfig(image=ImageConfig(repository="manifest-repo", tag="manifest-tag")),
    )
    defaults.update(kwargs)
    return AgentManifest(**defaults)


@pytest.fixture
def fixed_acp_module(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(deploy_handlers, "calculate_docker_acp_module", lambda manifest, path: "resolved.module")


class TestMergeDeploymentConfigsWrapper:
    def test_matches_slim_module_output(self, fixed_acp_module) -> None:
        manifest = make_manifest()
        wrapper_values = merge_deployment_configs(manifest, None, InputDeployOverrides(), "manifest.yaml")
        core_values = merge_helm_values(
            manifest, None, repository="manifest-repo", image_tag="manifest-tag", acp_module="resolved.module"
        )
        assert wrapper_values == core_values

    def test_deploy_overrides_win_over_manifest_image(self, fixed_acp_module) -> None:
        overrides = InputDeployOverrides(repository="override-repo", image_tag="override-tag")
        helm_values = merge_deployment_configs(make_manifest(), None, overrides, "manifest.yaml")
        assert helm_values["global"]["image"]["repository"] == "override-repo"
        assert helm_values["global"]["image"]["tag"] == "override-tag"

    def test_missing_deployment_raises_deployment_error(self) -> None:
        with pytest.raises(DeploymentError, match="No deployment configuration"):
            merge_deployment_configs(make_manifest(deployment=None), None, InputDeployOverrides(), "manifest.yaml")

    def test_value_error_from_core_maps_to_deployment_error(self, fixed_acp_module) -> None:
        env_config = AgentEnvironmentConfig(auth=AgentAuthConfig(principal={}))
        with pytest.raises(DeploymentError, match="Auth principal unable to be encoded"):
            merge_deployment_configs(make_manifest(), env_config, InputDeployOverrides(), "manifest.yaml")

    def test_unresolvable_acp_module_falls_back_to_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def boom(manifest, path):
            raise RuntimeError("no source tree")

        monkeypatch.setattr(deploy_handlers, "calculate_docker_acp_module", boom)
        helm_values = merge_deployment_configs(make_manifest(), None, InputDeployOverrides(), "manifest.yaml")
        assert helm_values["command"][1] == "project.acp:acp"

    def test_module_resolution_skipped_when_command_overridden(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fail_if_called(manifest, path):
            raise AssertionError("calculate_docker_acp_module should not run when command is overridden")

        monkeypatch.setattr(deploy_handlers, "calculate_docker_acp_module", fail_if_called)
        env_config = AgentEnvironmentConfig(
            auth=AgentAuthConfig(principal={"user_id": "u1"}),
            helm_overrides={"command": ["python", "-m", "custom"]},
        )
        helm_values = merge_deployment_configs(make_manifest(), env_config, InputDeployOverrides(), "manifest.yaml")
        assert helm_values["command"] == ["python", "-m", "custom"]


class TestBackCompatReExports:
    def test_historical_names_still_importable(self) -> None:
        from agentex.lib.cli.handlers.deploy_handlers import (  # noqa: F401
            TEMPORAL_WORKER_KEY,
            _deep_merge,
            convert_env_vars_dict_to_list,
            add_acp_command_to_helm_values,
        )

    def test_add_acp_command_to_helm_values_still_writes_command(self, fixed_acp_module) -> None:
        helm_values: dict = {}
        deploy_handlers.add_acp_command_to_helm_values(helm_values, make_manifest(), "manifest.yaml")
        assert helm_values["command"] == ["uvicorn", "resolved.module:acp", "--host", "0.0.0.0", "--port", "8000"]
