from pydantic import BaseModel, Field


class CredentialMapping(BaseModel):
    """Maps a Kubernetes secret to an environment variable in the agent container.

    This allows agents to securely access credentials stored in Kubernetes secrets
    by mapping them to environment variables. For example, you can map a secret
    containing an API key to an environment variable that your agent code expects.

    Example:
        A mapping of {"env_var_name": "OPENAI_API_KEY",
                     "secret_name": "ai-credentials",
                     "secret_key": "openai-key"}
        will make the value from the "openai-key" field in the "ai-credentials"
        Kubernetes secret available to the agent as OPENAI_API_KEY environment variable.

    Attributes:
        env_var_name: The name of the environment variable that will be available to the agent
        secret_name: The name of the Kubernetes secret containing the credential
        secret_key: The key within the Kubernetes secret that contains the credential value
    """

    env_var_name: str = Field(
        ...,
        description="Name of the environment variable that will be available to the agent",
    )
    secret_name: str = Field(
        ..., description="Name of the Kubernetes secret containing the credential"
    )
    secret_key: str = Field(
        ...,
        description="Key within the Kubernetes secret that contains the credential value",
    )
