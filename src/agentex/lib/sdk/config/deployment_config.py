from typing import Any, Dict

from pydantic import Field

from agentex.lib.utils.model_utils import BaseModel


class ImageConfig(BaseModel):
    """Configuration for container images"""

    repository: str = Field(..., description="Container image repository URL")
    tag: str = Field(default="latest", description="Container image tag")


class ImagePullSecretConfig(BaseModel):
    """Configuration for image pull secrets"""

    name: str = Field(..., description="Name of the image pull secret")


class ResourceRequirements(BaseModel):
    """Resource requirements for containers"""

    cpu: str = Field(
        default="500m", description="CPU request/limit (e.g., '500m', '1')"
    )
    memory: str = Field(
        default="1Gi", description="Memory request/limit (e.g., '1Gi', '512Mi')"
    )


class ResourceConfig(BaseModel):
    """Resource configuration for containers"""

    requests: ResourceRequirements = Field(
        default_factory=ResourceRequirements, description="Resource requests"
    )
    limits: ResourceRequirements = Field(
        default_factory=ResourceRequirements, description="Resource limits"
    )


class GlobalDeploymentConfig(BaseModel):
    """Global deployment configuration that applies to all clusters"""

    agent: dict[str, str] = Field(
        default_factory=dict, description="Agent metadata (name, description)"
    )
    replicaCount: int = Field(default=1, description="Number of replicas to deploy")
    resources: ResourceConfig = Field(
        default_factory=ResourceConfig, description="Resource requirements"
    )


class DeploymentConfig(BaseModel):
    """Main deployment configuration in the manifest"""

    image: ImageConfig = Field(..., description="Container image configuration")
    imagePullSecrets: list[ImagePullSecretConfig] | None = Field(
        default=None, description="Image pull secrets to use for the deployment"
    )
    global_config: GlobalDeploymentConfig = Field(
        default_factory=GlobalDeploymentConfig,
        description="Global deployment settings",
        alias="global",
    )

    class Config:
        validate_by_name = True


class ClusterConfig(BaseModel):
    """Per-cluster deployment overrides"""

    image: ImageConfig | None = Field(
        default=None, description="Cluster-specific image overrides"
    )
    replicaCount: int | None = Field(
        default=None, description="Cluster-specific replica count"
    )
    resources: ResourceConfig | None = Field(
        default=None, description="Cluster-specific resource overrides"
    )
    env: list[dict[str, str]] | None = Field(
        default=None, description="Additional environment variables for this cluster"
    )
    # Allow additional arbitrary overrides for advanced users
    additional_overrides: dict[str, Any] | None = Field(
        default=None, description="Additional helm chart value overrides"
    )


class AuthenticationConfig(BaseModel):
    principal: Dict[str, Any] = Field(description="Principal used for authorization on registration")


class InjectedImagePullSecretValues(BaseModel):
    """Values for image pull secrets"""

    registry: str = Field(..., description="Registry of the image pull secret")
    username: str = Field(..., description="Username of the image pull secret")
    password: str = Field(..., description="Password of the image pull secret")
    email: str | None = Field(
        default=None, description="Email of the image pull secret"
    )


class InjectedSecretsValues(BaseModel):
    """Values for injected secrets"""

    # Defined as a dictionary because the names need to be unique
    credentials: dict[str, Any] = Field(
        default_factory=dict, description="Secrets to inject into the deployment"
    )
    imagePullSecrets: dict[str, InjectedImagePullSecretValues] = Field(
        default_factory=dict,
        description="Image pull secrets to inject into the deployment",
    )

    class Config:
        validate_by_name = True
