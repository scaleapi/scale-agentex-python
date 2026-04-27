"""Tests for the auth-principal portion of the environments.yaml validator.

Covers the rule that an env config's principal must carry exactly one of
`user_id` or `service_account_id` — the same shape that downstream services
(agentex-auth, SGP) expect on the wire.
"""

import pytest

from agentex.lib.sdk.config.validation import (
    EnvironmentsValidationError,
    validate_environments_config,
)
from agentex.lib.sdk.config.environment_config import (
    AgentAuthConfig,
    AgentKubernetesConfig,
    AgentEnvironmentConfig,
    AgentEnvironmentsConfig,
)


def _config_with_principal(principal: dict) -> AgentEnvironmentsConfig:
    return AgentEnvironmentsConfig(
        schema_version="v1",
        environments={
            "dev": AgentEnvironmentConfig(
                kubernetes=AgentKubernetesConfig(namespace="dev-ns"),
                auth=AgentAuthConfig(principal=principal),
            )
        },
    )


def test_user_only_principal_passes():
    """Existing user_id-only configs continue to validate (backwards compat)."""
    config = _config_with_principal({"user_id": "73d0c8bd-4726-434c-9686-eb627d89f078", "account_id": "acct-1"})

    validate_environments_config(config)


def test_service_account_only_principal_passes():
    """New service_account_id-only configs validate."""
    config = _config_with_principal(
        {"service_account_id": "a1b2c3d4-5e6f-7a8b-9c0d-1e2f3a4b5c6d", "account_id": "acct-1"}
    )

    validate_environments_config(config)


def test_principal_with_neither_id_is_rejected():
    """A principal with no identity id fails fast with a clear error."""
    config = _config_with_principal({"account_id": "acct-1"})

    with pytest.raises(EnvironmentsValidationError) as exc_info:
        validate_environments_config(config)

    msg = str(exc_info.value)
    assert "user_id" in msg
    assert "service_account_id" in msg


def test_principal_with_both_ids_is_rejected():
    """Setting both ids is a config error — the principal must commit to one identity type."""
    config = _config_with_principal(
        {
            "user_id": "73d0c8bd-4726-434c-9686-eb627d89f078",
            "service_account_id": "a1b2c3d4-5e6f-7a8b-9c0d-1e2f3a4b5c6d",
            "account_id": "acct-1",
        }
    )

    with pytest.raises(EnvironmentsValidationError) as exc_info:
        validate_environments_config(config)

    msg = str(exc_info.value)
    assert "only one of" in msg.lower() or "not both" in msg.lower()
