"""Tests for AgentEnvironmentsConfig."""

import tempfile

import pytest

from agentex.lib.sdk.config.environment_config import (
    AgentAuthConfig,
    AgentKubernetesConfig,
    AgentEnvironmentConfig,
    AgentEnvironmentsConfig,
)


class TestAgentEnvironmentsConfig:
    """Test cases for AgentEnvironmentsConfig.get_config_for_env method."""

    @pytest.fixture
    def single_env_config(self) -> AgentEnvironmentsConfig:
        """Config with a single environment using direct key name."""
        return AgentEnvironmentsConfig(
            schema_version="v1",
            environments={
                "dev": AgentEnvironmentConfig(
                    kubernetes=AgentKubernetesConfig(namespace="dev-ns"),
                    auth=AgentAuthConfig(principal={"user_id": "dev-user"}),
                )
            },
        )

    @pytest.fixture
    def multi_env_config(self) -> AgentEnvironmentsConfig:
        """Config with multiple environments using direct key names."""
        return AgentEnvironmentsConfig(
            schema_version="v1",
            environments={
                "dev": AgentEnvironmentConfig(
                    kubernetes=AgentKubernetesConfig(namespace="dev-ns"),
                    auth=AgentAuthConfig(principal={"user_id": "dev-user"}),
                ),
                "staging": AgentEnvironmentConfig(
                    kubernetes=AgentKubernetesConfig(namespace="staging-ns"),
                    auth=AgentAuthConfig(principal={"user_id": "staging-user"}),
                ),
                "prod": AgentEnvironmentConfig(
                    kubernetes=AgentKubernetesConfig(namespace="prod-ns"),
                    auth=AgentAuthConfig(principal={"user_id": "prod-user"}),
                ),
            },
        )

    @pytest.fixture
    def multi_cluster_same_env_config(self) -> AgentEnvironmentsConfig:
        """Config with multiple clusters mapping to the same environment keyword."""
        return AgentEnvironmentsConfig(
            schema_version="v1",
            environments={
                "dev-aws": AgentEnvironmentConfig(
                    kubernetes=AgentKubernetesConfig(namespace="dev-ns-aws"),
                    environment="dev",
                    auth=AgentAuthConfig(principal={"user_id": "dev-aws-user"}),
                ),
                "dev-gcp": AgentEnvironmentConfig(
                    kubernetes=AgentKubernetesConfig(namespace="dev-ns-gcp"),
                    environment="dev",
                    auth=AgentAuthConfig(principal={"user_id": "dev-gcp-user"}),
                ),
                "prod": AgentEnvironmentConfig(
                    kubernetes=AgentKubernetesConfig(namespace="prod-ns"),
                    auth=AgentAuthConfig(principal={"user_id": "prod-user"}),
                ),
            },
        )

    def test_get_config_by_exact_key_match(self, single_env_config: AgentEnvironmentsConfig):
        """Test that exact key match returns the correct config."""
        result = single_env_config.get_config_for_env("dev")
        assert result is not None

    def test_get_config_nonexistent_env_raises_error(self, single_env_config: AgentEnvironmentsConfig):
        """Test that requesting non-existent environment raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            single_env_config.get_config_for_env("nonexistent")

    def test_get_config_exact_key_with_multiple_envs(self, multi_env_config: AgentEnvironmentsConfig):
        """Test getting config by exact key when multiple environments exist."""
        result = multi_env_config.get_config_for_env("staging")
        assert result is not None

    def test_get_config_by_specific_cluster_name(self, multi_cluster_same_env_config: AgentEnvironmentsConfig):
        """Test getting config by specific cluster name (e.g., dev-aws)."""
        result = multi_cluster_same_env_config.get_config_for_env("dev-aws")
        assert result is not None

    def test_get_configs_without_explicit_mapping(self, single_env_config: AgentEnvironmentsConfig):
        """Test getting config without explicit mapping returns a dict with env name as key."""
        result = single_env_config.get_configs_for_env("dev")
        assert isinstance(result, dict)
        assert len(result) == 1
        assert "dev" in result
        assert result["dev"] == single_env_config.get_config_for_env("dev")

    def test_multiple_envs_same_keyword_returns_multiple(self, multi_cluster_same_env_config: AgentEnvironmentsConfig):
        """Test that querying 'dev' when multiple envs have environment='dev' returns multiple.

        Returns a dict mapping env names (dev-aws, dev-gcp) to their configs.
        """
        result = multi_cluster_same_env_config.get_configs_for_env("dev")
        assert isinstance(result, dict)
        assert len(result) == 2
        assert "dev-aws" in result
        assert "dev-gcp" in result
        assert result["dev-aws"].kubernetes.namespace == "dev-ns-aws"
        assert result["dev-gcp"].kubernetes.namespace == "dev-ns-gcp"

    def test_list_environments(self, multi_env_config: AgentEnvironmentsConfig):
        """Test listing all environment names."""
        envs = multi_env_config.list_environments()
        assert set(envs) == {"dev", "staging", "prod"}


class TestAgentEnvironmentsConfigFromYaml:
    """Test cases for AgentEnvironmentsConfig.from_yaml method."""

    def test_load_single_env_yaml(self):
        """Test loading a YAML file with a single environment."""
        yaml_content = """
schema_version: v1
environments:
  dev:
    kubernetes:
      namespace: dev-namespace
    auth:
      principal:
        user_id: "user-123"
        account_id: "account-456"
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()

            config = AgentEnvironmentsConfig.from_yaml(f.name)

            assert config.schema_version == "v1"
            assert "dev" in config.environments
            assert config.environments["dev"].kubernetes.namespace == "dev-namespace"
            assert config.environments["dev"].auth.principal["user_id"] == "user-123"

    def test_load_multi_env_yaml(self):
        """Test loading a YAML file with multiple environments."""
        yaml_content = """
schema_version: v1
environments:
  dev:
    kubernetes:
      namespace: dev-namespace
    auth:
      principal:
        user_id: "dev-user"
        account_id: "dev-account"
  prod:
    kubernetes:
      namespace: prod-namespace
    auth:
      principal:
        user_id: "prod-user"
        account_id: "prod-account"
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()

            config = AgentEnvironmentsConfig.from_yaml(f.name)

            assert "dev" in config.environments
            assert "prod" in config.environments
            assert config.environments["dev"].kubernetes.namespace == "dev-namespace"
            assert config.environments["prod"].kubernetes.namespace == "prod-namespace"

    def test_load_yaml_with_environment_field_mapping(self):
        """Test loading YAML where environments use the 'environment' field for mapping."""
        yaml_content = """
schema_version: v1
environments:
  dev-aws:
    environment: dev
    kubernetes:
      namespace: dev-aws-ns
    auth:
      principal:
        user_id: "aws-user"
  dev-gcp:
    environment: dev
    kubernetes:
      namespace: dev-gcp-ns
    auth:
      principal:
        user_id: "gcp-user"
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()

            config = AgentEnvironmentsConfig.from_yaml(f.name)

            assert config.environments["dev-aws"].environment == "dev"
            assert config.environments["dev-gcp"].environment == "dev"
            assert config.environments["dev-aws"].kubernetes.namespace == "dev-aws-ns"
            assert config.environments["dev-gcp"].kubernetes.namespace == "dev-gcp-ns"

    def test_load_yaml_with_helm_overrides(self):
        """Test loading YAML with helm_overrides."""
        yaml_content = """
schema_version: v1
environments:
  dev:
    kubernetes:
      namespace: dev-namespace
    auth:
      principal:
        user_id: "user-123"
    helm_overrides:
      replicaCount: 3
      resources:
        requests:
          cpu: "500m"
          memory: "1Gi"
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()

            config = AgentEnvironmentsConfig.from_yaml(f.name)

            assert config.environments["dev"].helm_overrides["replicaCount"] == 3
            assert config.environments["dev"].helm_overrides["resources"]["requests"]["cpu"] == "500m"

    def test_load_yaml_with_custom_helm_repo(self):
        """Test loading YAML with custom helm repository settings."""
        yaml_content = """
schema_version: v1
environments:
  dev:
    kubernetes:
      namespace: dev-namespace
    auth:
      principal:
        user_id: "user-123"
    helm_repository_name: custom-repo
    helm_repository_url: https://custom.example.com/charts
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()

            config = AgentEnvironmentsConfig.from_yaml(f.name)

            assert config.environments["dev"].helm_repository_name == "custom-repo"
            assert config.environments["dev"].helm_repository_url == "https://custom.example.com/charts"

    def test_load_nonexistent_yaml_raises_file_not_found(self):
        """Test that loading non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="environments.yaml not found"):
            AgentEnvironmentsConfig.from_yaml("/nonexistent/path/environments.yaml")

    def test_load_empty_yaml_raises_value_error(self):
        """Test that loading empty YAML file raises ValueError."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("")
            f.flush()

            with pytest.raises(ValueError, match="empty"):
                AgentEnvironmentsConfig.from_yaml(f.name)

    def test_load_invalid_yaml_syntax_raises_value_error(self):
        """Test that loading invalid YAML syntax raises ValueError."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("invalid: yaml: content: [")
            f.flush()

            with pytest.raises(ValueError, match="Invalid YAML"):
                AgentEnvironmentsConfig.from_yaml(f.name)

    def test_load_yaml_missing_required_auth_raises_error(self):
        """Test that YAML missing required 'auth' field raises validation error."""
        yaml_content = """
schema_version: v1
environments:
  dev:
    kubernetes:
      namespace: dev-namespace
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()

            with pytest.raises(ValueError, match="Failed to load"):
                AgentEnvironmentsConfig.from_yaml(f.name)
