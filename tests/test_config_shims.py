"""Tests that pin the back-compat contract for config-model shims.

The canonical location for deployment/agent configuration models is
:mod:`agentex.config` (mirroring PR scaleapi/scale-agentex-python#371, which
did this for protocol types). The historical locations under
:mod:`agentex.lib.sdk.config.*` and :mod:`agentex.lib.types.*` are preserved as
re-export shims so external consumers' existing imports continue to work.

These tests enforce:

1. **Symbol parity** — every public name the original modules exported is
   still importable from the old path.
2. **Identity** — the class objects at the shim path are the *same* objects as
   the canonical path, so ``isinstance`` stays correct across import styles.
3. **Config preservation** — the swap from ``model_utils.BaseModel`` to plain
   pydantic kept ``populate_by_name`` (``DeploymentConfig``'s ``global`` alias
   relies on it; it previously also carried a now-removed
   ``class Config: validate_by_name``).
"""

from __future__ import annotations


def test_config_shims_re_export_all_original_symbols() -> None:
    """Every name historically exported from the old paths must still be
    importable from those paths via the back-compat shims."""
    from agentex.lib.types.credentials import CredentialMapping  # noqa: F401
    from agentex.lib.types.agent_configs import (  # noqa: F401
        TemporalConfig,
        TemporalWorkerConfig,
        TemporalWorkflowConfig,
    )
    from agentex.lib.sdk.config.agent_config import AgentConfig  # noqa: F401
    from agentex.lib.sdk.config.build_config import (  # noqa: F401
        BuildConfig,
        BuildContext,
    )
    from agentex.lib.sdk.config.agent_manifest import (  # noqa: F401
        AgentManifest,
        BuildContextManager,
        load_agent_manifest,
        build_context_manager,
    )
    from agentex.lib.sdk.config.deployment_config import (  # noqa: F401
        ImageConfig,
        ClusterConfig,
        ResourceConfig,
        DeploymentConfig,
        AuthenticationConfig,
        ResourceRequirements,
        ImagePullSecretConfig,
        InjectedSecretsValues,
        GlobalDeploymentConfig,
        InjectedImagePullSecretValues,
    )
    from agentex.lib.sdk.config.environment_config import (  # noqa: F401
        AgentAuthConfig,
        OciRegistryConfig,
        AgentKubernetesConfig,
        AgentEnvironmentConfig,
        AgentEnvironmentsConfig,
        load_environments_config,
        load_environments_config_from_manifest_dir,
    )
    from agentex.lib.sdk.config.local_development_config import (  # noqa: F401
        LocalAgentConfig,
        LocalPathsConfig,
        LocalDevelopmentConfig,
    )


def test_config_shim_classes_are_identical_to_canonical() -> None:
    """Shim re-exports must be the *same* class objects as the canonical path.
    Different objects would break ``isinstance`` for code that mixes import
    styles."""
    from agentex.config import (
        credentials,
        agent_config,
        build_config,
        agent_configs as canon_agent_configs,
        agent_manifest as canon_manifest,
        deployment_config as canon_deploy,
        environment_config as canon_env,
        local_development_config as canon_local,
    )
    from agentex.lib.types import credentials as shim_creds, agent_configs as shim_agent_configs
    from agentex.lib.sdk.config import (
        agent_config as shim_agent_config,
        build_config as shim_build,
        agent_manifest as shim_manifest,
        deployment_config as shim_deploy,
        environment_config as shim_env,
        local_development_config as shim_local,
    )

    assert shim_agent_config.AgentConfig is agent_config.AgentConfig
    assert shim_build.BuildConfig is build_config.BuildConfig
    assert shim_deploy.DeploymentConfig is canon_deploy.DeploymentConfig
    assert shim_local.LocalDevelopmentConfig is canon_local.LocalDevelopmentConfig
    assert shim_env.AgentEnvironmentsConfig is canon_env.AgentEnvironmentsConfig
    assert shim_env.AgentEnvironmentConfig is canon_env.AgentEnvironmentConfig
    assert shim_agent_configs.TemporalConfig is canon_agent_configs.TemporalConfig
    assert shim_creds.CredentialMapping is credentials.CredentialMapping
    assert shim_manifest.AgentManifest is canon_manifest.AgentManifest


def test_deployment_config_populates_global_by_name_and_alias() -> None:
    """``populate_by_name`` (inherited via ConfigBaseModel) must let the
    ``global``-aliased field be set by either its field name or its alias —
    the swap dropped the legacy ``class Config: validate_by_name``."""
    from agentex.config.deployment_config import DeploymentConfig

    by_name = DeploymentConfig.model_validate({"image": {"repository": "r"}, "global_config": {"replicaCount": 2}})
    assert by_name.global_config.replicaCount == 2

    by_alias = DeploymentConfig.model_validate({"image": {"repository": "r"}, "global": {"replicaCount": 3}})
    assert by_alias.global_config.replicaCount == 3
