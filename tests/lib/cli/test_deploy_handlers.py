"""Tests for helm value merging in deploy_handlers."""

from __future__ import annotations

from typing import Any

import pytest

from agentex.config.agent_config import AgentConfig
from agentex.config.build_config import BuildConfig, BuildContext
from agentex.config.agent_configs import TemporalConfig, TemporalWorkflowConfig
from agentex.config.agent_manifest import AgentManifest
from agentex.config.deployment_config import ImageConfig, DeploymentConfig
from agentex.config.environment_config import AgentAuthConfig, AgentEnvironmentConfig
from agentex.lib.cli.handlers.deploy_handlers import (
    TEMPORAL_WORKER_KEY,
    InputDeployOverrides,
    merge_deployment_configs,
)


def _manifest(*, temporal: bool) -> AgentManifest:
    return AgentManifest(
        build=BuildConfig(context=BuildContext(root=".", dockerfile="Dockerfile", dockerignore=None)),
        agent=AgentConfig(
            name="test-agent",
            acp_type="async",
            description="An AgentEx agent",
            temporal=TemporalConfig(
                enabled=True,
                workflows=[TemporalWorkflowConfig(name="test-agent", queue_name="test_agent_queue")],
            )
            if temporal
            else None,
        ),
        deployment=DeploymentConfig(image=ImageConfig(repository="registry.example.com/test-agent", tag="v1")),
    )


def _env_config(helm_overrides: dict[str, Any] | None = None) -> AgentEnvironmentConfig:
    return AgentEnvironmentConfig(
        auth=AgentAuthConfig(principal={"user_id": "test-user", "account_id": "test-account"}),
        helm_overrides=helm_overrides or {},
    )


def _merge(*, temporal: bool = False, env_config: AgentEnvironmentConfig | None = None) -> dict[str, Any]:
    return merge_deployment_configs(
        manifest=_manifest(temporal=temporal),
        agent_env_config=env_config,
        deploy_overrides=InputDeployOverrides(),
        manifest_path="manifest.yaml",
    )


class TestAutoscalingDefaults:
    """Autoscaling is opt-in, and the bounds stay available for whoever opts in."""

    def test_disabled_by_default(self):
        assert _merge()["autoscaling"]["enabled"] is False

    def test_disabled_by_default_for_temporal_worker(self):
        helm_values = _merge(temporal=True)
        assert helm_values[TEMPORAL_WORKER_KEY]["autoscaling"]["enabled"] is False

    @pytest.mark.parametrize(
        "key,expected", [("minReplicas", 1), ("maxReplicas", 10), ("targetCPUUtilizationPercentage", 50)]
    )
    def test_bounds_survive_an_opt_in(self, key: str, expected: int):
        """An opt-in that sets only `enabled` must still inherit the CPU target and replica bounds."""
        helm_values = _merge(env_config=_env_config({"autoscaling": {"enabled": True}}))

        assert helm_values["autoscaling"]["enabled"] is True
        assert helm_values["autoscaling"][key] == expected

    def test_temporal_worker_opts_in_separately(self):
        """The worker HPA is its own block, so opting the agent in leaves the worker off."""
        helm_values = _merge(
            temporal=True,
            env_config=_env_config({"autoscaling": {"enabled": True}}),
        )

        assert helm_values["autoscaling"]["enabled"] is True
        assert helm_values[TEMPORAL_WORKER_KEY]["autoscaling"]["enabled"] is False

        opted_in = _merge(
            temporal=True,
            env_config=_env_config({TEMPORAL_WORKER_KEY: {"autoscaling": {"enabled": True}}}),
        )

        assert opted_in[TEMPORAL_WORKER_KEY]["autoscaling"]["enabled"] is True
        assert opted_in[TEMPORAL_WORKER_KEY]["autoscaling"]["targetCPUUtilizationPercentage"] == 50

    def test_opt_in_overrides_win_over_the_base(self):
        helm_values = _merge(env_config=_env_config({"autoscaling": {"enabled": True, "maxReplicas": 3}}))

        assert helm_values["autoscaling"]["maxReplicas"] == 3
        assert helm_values["autoscaling"]["targetCPUUtilizationPercentage"] == 50
