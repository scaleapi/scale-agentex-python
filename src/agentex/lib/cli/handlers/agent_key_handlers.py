"""Deploy-time delivery of the agent's internal API key for `agentex agents deploy`.

The key is issued by the Agentex server, stored once in a per-agent Kubernetes Secret in the
deployment namespace, and handed to the agent and Temporal worker pods only as a
``secretKeyRef``. The key value never appears in Helm values, logs, or exceptions.
"""

from __future__ import annotations

import hashlib
from typing import Any, cast

from kubernetes import client
from rich.console import Console
from kubernetes.client.rest import ApiException

from agentex import Agentex, ConflictError
from agentex.lib.utils.logging import make_logger
from agentex.config.agent_manifest import AgentManifest
from agentex.lib.cli.utils.exceptions import DeploymentError
from agentex.lib.cli.utils.kubectl_utils import get_k8s_client

logger = make_logger(__name__)
console = Console()

AGENT_API_KEY_ENV_VAR = "AGENT_API_KEY"
AGENT_API_KEY_SECRET_DATA_KEY = "AGENT_API_KEY"
AGENT_API_KEY_SECRET_PREFIX = "agentex-agent-key"
AGENT_ID_ANNOTATION = "agentex.scale.com/agent-id"
MANAGED_BY_LABEL = "app.kubernetes.io/managed-by"
MANAGED_BY_VALUE = "agentex-cli"
TEMPORAL_WORKER_KEY = "temporal-worker"


def agent_api_key_secret_name(agent_id: str) -> str:
    """Return the stable per-agent Secret name without exposing the agent id."""
    digest = hashlib.sha256(agent_id.encode("utf-8")).hexdigest()[:16]
    return f"{AGENT_API_KEY_SECRET_PREFIX}-{digest}"


def reject_reserved_agent_api_key_values(helm_values: dict[str, Any]) -> None:
    """Fail if caller configuration already sets AGENT_API_KEY or points at a managed Secret."""
    sections = [("", helm_values)]
    worker = helm_values.get(TEMPORAL_WORKER_KEY)
    if isinstance(worker, dict):
        sections.append((f"{TEMPORAL_WORKER_KEY}.", worker))
    for prefix, section in sections:
        for key in ("env", "secretEnvVars"):
            entries = section.get(key)
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                if entry.get("name") == AGENT_API_KEY_ENV_VAR:
                    raise DeploymentError(
                        f"{prefix}{key} sets {AGENT_API_KEY_ENV_VAR}, which is managed by "
                        "`agentex agents deploy --agent-key`. Remove it from the manifest, "
                        "credentials, and helm_overrides."
                    )
                secret_name = entry.get("secretName")
                if isinstance(secret_name, str) and secret_name.startswith(f"{AGENT_API_KEY_SECRET_PREFIX}-"):
                    raise DeploymentError(
                        f"{prefix}{key} references the managed Secret {secret_name!r}; "
                        f"names starting with {AGENT_API_KEY_SECRET_PREFIX!r} are reserved."
                    )


def inject_agent_api_key_secret_ref(helm_values: dict[str, Any], secret_name: str) -> None:
    """Add the managed AGENT_API_KEY secretKeyRef to the agent and, if present, the Temporal worker."""
    reject_reserved_agent_api_key_values(helm_values)
    entry = {
        "name": AGENT_API_KEY_ENV_VAR,
        "secretName": secret_name,
        "secretKey": AGENT_API_KEY_SECRET_DATA_KEY,
    }
    helm_values.setdefault("secretEnvVars", []).append(dict(entry))
    worker = helm_values.get(TEMPORAL_WORKER_KEY)
    if isinstance(worker, dict):
        worker.setdefault("secretEnvVars", []).append(dict(entry))


def _secret_body(name: str, agent_id: str, value: str) -> client.V1Secret:
    return client.V1Secret(
        metadata=client.V1ObjectMeta(
            name=name,
            labels={MANAGED_BY_LABEL: MANAGED_BY_VALUE},
            annotations={AGENT_ID_ANNOTATION: agent_id},
        ),
        type="Opaque",
        string_data={AGENT_API_KEY_SECRET_DATA_KEY: value},
    )


def _read_stored_key(v1: client.CoreV1Api, namespace: str, name: str, agent_id: str) -> bool:
    """Return whether a usable managed Secret for this agent already exists."""
    try:
        secret = cast(client.V1Secret, v1.read_namespaced_secret(name=name, namespace=namespace))
    except ApiException as e:
        if e.status == 404:
            return False
        raise DeploymentError(f"Could not read managed Secret {name!r} in namespace {namespace!r}") from None
    annotations = (secret.metadata.annotations or {}) if secret.metadata else {}
    if annotations.get(AGENT_ID_ANNOTATION) != agent_id:
        raise DeploymentError(
            f"Secret {name!r} in namespace {namespace!r} is not the managed key for this agent; "
            "refusing to reuse or overwrite it."
        )
    if not (secret.data or {}).get(AGENT_API_KEY_SECRET_DATA_KEY):
        raise DeploymentError(f"Managed Secret {name!r} in namespace {namespace!r} has no key data.")
    return True


def _provision_internal_key(agentex_client: Agentex, agent_id: str, *, replace: bool) -> str | None:
    """Issue (or replay) the agent's internal key. Returns None when Agentex reports an existing key."""
    try:
        response = agentex_client.post(
            f"/agents/{agent_id}/internal-key",
            body={"replace": True} if replace else {},
            cast_to=object,
        )
    except ConflictError:
        return None
    except Exception:
        # Never attach the original exception: a parsing failure could carry the issued key.
        raise DeploymentError(f"Agentex failed to provision an internal key for agent {agent_id}.") from None
    if not isinstance(response, dict) or response.get("agent_id") != agent_id:
        raise DeploymentError("Agentex returned an internal key for a different agent.")
    value = response.get("agent_api_key")
    if not isinstance(value, str) or not value:
        raise DeploymentError("Agentex returned an invalid internal key response.")
    return value


def bootstrap_agent_api_key(
    *,
    agentex_client: Agentex,
    manifest: AgentManifest,
    namespace: str,
    context: str | None = None,
    replace_existing_key: bool = False,
) -> str:
    """Register the agent and make sure its internal key is stored; return the Secret name.

    Every step that can fail runs before Helm changes the release, so a failure leaves the
    running deployment untouched.
    """
    try:
        agent = agentex_client.agents.register_build(
            name=manifest.agent.name,
            description=manifest.agent.description or "",
        )
    except Exception as e:
        raise DeploymentError(f"Failed to register agent {manifest.agent.name!r} with Agentex: {e}") from e
    agent_id = agent.id
    secret_name = agent_api_key_secret_name(agent_id)
    v1 = get_k8s_client(context)

    if _read_stored_key(v1, namespace, secret_name, agent_id):
        if replace_existing_key:
            raise DeploymentError(
                f"Managed Secret {secret_name!r} already exists; --replace-agent-key only migrates "
                "agents that have no stored key."
            )
        console.print(f"[green]✓[/green] Reusing stored agent key Secret {secret_name}")
        return secret_name

    # Kubernetes must accept the Secret before Agentex returns the only readable copy of a new key.
    try:
        v1.create_namespaced_secret(
            namespace=namespace,
            body=_secret_body(secret_name, agent_id, "preflight"),
            dry_run="All",
        )
    except ApiException:
        raise DeploymentError(
            f"Kubernetes would not accept Secret {secret_name!r} in namespace {namespace!r}; no agent key was issued."
        ) from None

    value = _provision_internal_key(agentex_client, agent_id, replace=replace_existing_key)
    if value is None:
        raise DeploymentError(
            f"Agent {manifest.agent.name!r} already has an internal key that this deploy cannot read, "
            "and no stored Secret was found. Migrate it with --replace-agent-key during a "
            "maintenance window: replacement revokes the running pods' key until the rollout completes."
        )

    try:
        v1.create_namespaced_secret(namespace=namespace, body=_secret_body(secret_name, agent_id, value))
    except ApiException as e:
        if e.status == 409 and _read_stored_key(v1, namespace, secret_name, agent_id):
            # A concurrent deploy stored the key first; Agentex returned that same key to both.
            return secret_name
        retry_hint = "without --replace-agent-key " if replace_existing_key else ""
        raise DeploymentError(
            f"Agentex issued an agent key, but Secret {secret_name!r} could not be stored. Retry the "
            f"deploy {retry_hint}within 10 minutes so Agentex replays the same key."
        ) from None
    console.print(f"[green]✓[/green] Stored agent key in Secret {secret_name}")
    return secret_name
