import base64
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import questionary
import typer
import yaml
from kubernetes.client.rest import ApiException
from rich.console import Console

from agentex.lib.cli.utils.cli_utils import handle_questionary_cancellation
from agentex.lib.cli.utils.kubectl_utils import get_k8s_client
from agentex.lib.cli.utils.kubernetes_secrets_utils import (
    KUBERNETES_SECRET_TO_MANIFEST_KEY,
    KUBERNETES_SECRET_TYPE_DOCKERCONFIGJSON,
    KUBERNETES_SECRET_TYPE_OPAQUE,
    VALID_SECRET_TYPES,
    create_image_pull_secret_with_data,
    create_secret_with_data,
    get_secret_data,
    update_image_pull_secret_with_data,
    update_secret_with_data,
)
from agentex.lib.sdk.config.agent_config import AgentConfig
from agentex.lib.sdk.config.agent_manifest import AgentManifest
from agentex.lib.sdk.config.deployment_config import (
    DeploymentConfig,
    ImagePullSecretConfig,
    InjectedSecretsValues,
)
from agentex.lib.types.credentials import CredentialMapping
from agentex.lib.utils.logging import make_logger

logger = make_logger(__name__)
console = Console()


# TODO: parse this into a Pydantic model.
def load_values_file(values_path: str) -> dict[str, dict[str, str]]:
    """Load and parse the values file (YAML/JSON)"""
    try:
        path = Path(values_path)
        content = path.read_text()

        if path.suffix.lower() in [".yaml", ".yml"]:
            data = yaml.safe_load(content)
        elif path.suffix.lower() == ".json":
            data = json.loads(content)
        else:
            # Try YAML first, then JSON
            try:
                data = yaml.safe_load(content)
            except yaml.YAMLError:
                data = json.loads(content)
        return InjectedSecretsValues.model_validate(data).model_dump()

    except Exception as e:
        raise RuntimeError(
            f"Failed to load values file '{values_path}': {str(e)}"
        ) from e


def interactive_secret_input(secret_name: str, secret_key: str) -> str:
    """Prompt user for secret value with appropriate input method"""
    console.print(
        f"\n[bold]Enter value for secret '[cyan]{secret_name}[/cyan]' key '[cyan]{secret_key}[/cyan]':[/bold]"
    )

    input_type = questionary.select(
        "What type of value is this?",
        choices=[
            "Simple text",
            "Sensitive/password (hidden input)",
            "Multi-line text",
            "JSON/YAML content",
            "Read from file",
        ],
    ).ask()

    input_type = handle_questionary_cancellation(input_type, "secret input")

    if input_type == "Sensitive/password (hidden input)":
        result = questionary.password("Enter value (input will be hidden):").ask()
        return handle_questionary_cancellation(result, "password input")

    elif input_type == "Multi-line text":
        console.print(
            "[yellow]Enter multi-line text (press Ctrl+D when finished):[/yellow]"
        )
        lines = []
        try:
            while True:
                line = input()
                lines.append(line)
        except EOFError:
            pass
        except KeyboardInterrupt:
            console.print("[yellow]Multi-line input cancelled by user[/yellow]")
            raise typer.Exit(0)  # noqa
        return "\n".join(lines)

    elif input_type == "JSON/YAML content":
        value = questionary.text("Enter JSON/YAML content:").ask()
        value = handle_questionary_cancellation(value, "JSON/YAML input")
        # Validate JSON/YAML format
        try:
            json.loads(value)
        except json.JSONDecodeError:
            try:
                yaml.safe_load(value)
            except yaml.YAMLError:
                console.print(
                    "[yellow]Warning: Content doesn't appear to be valid JSON or YAML[/yellow]"
                )
        return value

    elif input_type == "Read from file":
        file_path = questionary.path("Enter file path:").ask()
        file_path = handle_questionary_cancellation(file_path, "file path input")
        try:
            return Path(file_path).read_text().strip()
        except Exception as e:
            console.print(f"[red]Error reading file: {e}[/red]")
            manual_value = questionary.text("Enter value manually:").ask()
            return handle_questionary_cancellation(manual_value, "manual value input")

    else:  # Simple text
        result = questionary.text("Enter value:").ask()
        return handle_questionary_cancellation(result, "text input")


def get_secret(name: str, namespace: str, context: str | None = None) -> dict:
    """Get details about a secret"""
    v1 = get_k8s_client(context)

    try:
        secret = v1.read_namespaced_secret(name=name, namespace=namespace)
        return {
            "name": secret.metadata.name,
            "namespace": namespace,
            "created": secret.metadata.creation_timestamp.isoformat(),
            "exists": True,
        }
    except ApiException as e:
        if e.status == 404:
            console.print(
                f"[red]Error: Secret '{name}' not found in namespace '{namespace}'[/red]"
            )
            return {"name": name, "namespace": namespace, "exists": False}
        raise RuntimeError(f"Failed to get secret: {str(e)}") from e


def delete_secret(name: str, namespace: str, context: str | None = None) -> None:
    """Delete a secret"""
    v1 = get_k8s_client(context)

    try:
        v1.delete_namespaced_secret(name=name, namespace=namespace)
        console.print(
            f"[green]Deleted secret '{name}' from namespace '{namespace}'[/green]"
        )
    except ApiException as e:
        if e.status == 404:
            console.print(
                f"[red]Error: Secret '{name}' not found in namespace '{namespace}'[/red]"
            )
        else:
            console.print(f"[red]Error deleting secret: {e.reason}[/red]")
            raise RuntimeError(f"Failed to delete secret: {str(e)}") from e


def get_kubernetes_secrets_by_type(
    namespace: str, context: str | None = None
) -> dict[str, list[dict]]:
    """List metadata about secrets in the namespace"""
    v1 = get_k8s_client(context)

    try:
        secrets = v1.list_namespaced_secret(namespace=namespace)
        secret_type_to_secret = defaultdict(list)
        for secret in secrets.items:
            if secret.type in VALID_SECRET_TYPES:
                secret_type_to_secret[secret.type].append(
                    {
                        "name": secret.metadata.name,
                        "namespace": namespace,
                        "created": secret.metadata.creation_timestamp.isoformat(),
                    }
                )

        return secret_type_to_secret
    except ApiException as e:
        console.print(
            f"[red]Error listing secrets in namespace '{namespace}': {e.reason}[/red]"
        )
        raise RuntimeError(f"Failed to list secrets: {str(e)}") from e

    # NOTE: This corresponds with KUBERNETES_SECRET_TYPE_OPAQUE


def sync_user_defined_secrets(
    manifest_obj: AgentManifest,
    found_secrets: list[dict],
    values_data: dict[str, Any],
    cluster: str,
    namespace: str,
    interactive: bool,
    changes: dict[str, list[str]],
) -> None:
    """Sync user defined secrets between manifest, cluster, and values file"""
    console.print(
        f"[bold]Syncing user defined secrets to cluster: {cluster} namespace: {namespace}[/bold]"
    )

    # Get the secrets from the cluster using the specified namespace and cluster context
    cluster_secret_names = {secret["name"] for secret in found_secrets}
    # Get the secrets from the manifest
    agent_config: AgentConfig = manifest_obj.agent
    manifest_credentials: list[CredentialMapping] = agent_config.credentials or []

    if not manifest_credentials:
        console.print("[yellow]No credentials found in manifest[/yellow]")
        return

    # Build required secrets map from manifest
    required_secrets = {}  # {secret_name: {secret_key: env_var_name}}
    for cred in manifest_credentials:
        if cred.secret_name not in required_secrets:
            required_secrets[cred.secret_name] = {}
        required_secrets[cred.secret_name][cred.secret_key] = cred.env_var_name

    # Process each required secret
    for secret_name, required_keys in required_secrets.items():
        current_secret_data = get_secret_data(secret_name, namespace, cluster)
        new_secret_data = {}
        secret_needs_update = False

        # Process each required key in this secret
        for secret_key, _ in required_keys.items():
            current_value = current_secret_data.get(secret_key)

            # Get the new value
            if (
                values_data
                and secret_name in values_data
                and secret_key in values_data[secret_name]
            ):
                new_value = values_data[secret_name][secret_key]
            elif interactive:
                if current_value:
                    console.print(
                        f"[blue]Secret '{secret_name}' key '{secret_key}' already exists[/blue]"
                    )
                    update_choice = questionary.select(
                        "What would you like to do?",
                        choices=[
                            "Keep current value",
                            "Update with new value",
                            "Show current value",
                        ],
                    ).ask()
                    update_choice = handle_questionary_cancellation(
                        update_choice, "secret update choice"
                    )

                    if update_choice == "Show current value":
                        console.print(f"Current value: [dim]{current_value}[/dim]")
                        update_choice = questionary.select(
                            "What would you like to do?",
                            choices=["Keep current value", "Update with new value"],
                        ).ask()
                        update_choice = handle_questionary_cancellation(
                            update_choice, "secret update choice"
                        )

                    if update_choice == "Update with new value":
                        new_value = interactive_secret_input(secret_name, secret_key)
                    else:
                        new_value = current_value
                else:
                    console.print(
                        f"[yellow]Secret '{secret_name}' key '{secret_key}' does not exist[/yellow]"
                    )
                    new_value = interactive_secret_input(secret_name, secret_key)
            else:
                raise RuntimeError(
                    f"No value provided for secret '{secret_name}' key '{secret_key}'. Provide values file or use interactive mode."
                )

            # Must be a string because kubernetes always expects a
            new_value = str(new_value)
            new_secret_data[secret_key] = new_value

            # Check if value changed
            if current_value != new_value:
                secret_needs_update = True
            else:
                changes["noop"].append(
                    f"Secret '{secret_name}' key '{secret_key}' is up to date"
                )

        # Determine action needed
        if secret_name not in cluster_secret_names:
            changes["create"].append(
                f"Create secret '{secret_name}' with keys: {list(required_keys.keys())}"
            )
            create_secret_with_data(secret_name, new_secret_data, namespace, cluster)
        elif secret_needs_update:
            changes["update"].append(f"Update secret '{secret_name}' (values changed)")
            update_secret_with_data(secret_name, new_secret_data, namespace, cluster)

    # Handle orphaned secrets (in cluster but not in manifest)
    orphaned_secrets = cluster_secret_names - set(required_secrets.keys())
    if orphaned_secrets:
        console.print(
            f"\n[yellow]Warning: Found {len(orphaned_secrets)} secrets in cluster not defined in manifest:[/yellow]"
        )
        for secret in orphaned_secrets:
            console.print(f"  - {secret}")


def create_dockerconfigjson_string(
    registry: str, username: str, password: str, email: str | None = None
) -> str:
    """Create raw dockerconfigjson string data for use with Kubernetes string_data field"""
    # Create the auth field (base64 encoded username:password)
    auth_string = f"{username}:{password}"
    auth_b64 = base64.b64encode(auth_string.encode("utf-8")).decode("utf-8")

    # Build the auth entry
    auth_entry = {"username": username, "password": password, "auth": auth_b64}

    # Only include email if provided
    if email:
        auth_entry["email"] = email

    # Create the full dockerconfig structure
    docker_config = {"auths": {registry: auth_entry}}

    # Return raw JSON string (Kubernetes will handle base64 encoding when using string_data)
    return json.dumps(docker_config)


def parse_dockerconfigjson_data(input_data: str) -> dict[str, dict[str, str]]:
    """Parse existing dockerconfigjson data to extract registry credentials"""
    try:
        # Decode base64
        config = json.loads(input_data)

        # Extract auths section
        auths = config.get("auths", {})

        # Convert to comparable format: {registry: {username, password, email}}
        parsed_auths = {}
        for registry, auth_data in auths.items():
            # Try to decode the base64 auth field first
            username = ""
            password = ""
            if "auth" in auth_data:
                try:
                    auth_b64 = auth_data["auth"]
                    username_password = base64.b64decode(auth_b64).decode("utf-8")
                    if ":" in username_password:
                        username, password = username_password.split(":", 1)
                except Exception:
                    pass

            # Fall back to direct username/password fields if auth decode failed
            if not username:
                username = auth_data.get("username", "")
            if not password:
                password = auth_data.get("password", "")

            parsed_auths[registry] = {
                "username": username,
                "password": password,
                "email": auth_data.get("email", ""),
            }

        return parsed_auths
    except Exception:
        return {}  # If parsing fails, assume empty/invalid


def credentials_changed(
    current_auths: dict[str, dict[str, str]],
    new_registry: str,
    new_username: str,
    new_password: str,
    new_email: str = "",
) -> bool:
    """Check if credentials have actually changed"""

    # If registry doesn't exist in current, it's a change
    if new_registry not in current_auths:
        return True

    current_creds = current_auths[new_registry]
    # Compare each field
    if (
        current_creds.get("username", "") != new_username
        or current_creds.get("password", "") != new_password
        or current_creds.get("email", "") != (new_email or "")
    ):
        return True
    else:
        return False  # No changes detected


def interactive_image_pull_secret_input(secret_name: str) -> dict[str, str]:
    """Prompt user for image pull secret values"""
    console.print(
        f"\n[bold]Configure image pull secret '[cyan]{secret_name}[/cyan]':[/bold]"
    )

    registry = questionary.text(
        "Registry URL (e.g., docker.io, gcr.io, your-registry.com):",
        default="docker.io",
    ).ask()
    registry = handle_questionary_cancellation(registry, "registry input")

    username = questionary.text("Username:").ask()
    username = handle_questionary_cancellation(username, "username input")

    password = questionary.password("Password (input will be hidden):").ask()
    password = handle_questionary_cancellation(password, "password input")

    email_choice = questionary.confirm(
        "Do you want to include an email address? (optional)"
    ).ask()
    email_choice = handle_questionary_cancellation(email_choice, "email choice")
    email = ""
    if email_choice:
        email = questionary.text("Email address:").ask() or ""
        if email is None:  # Handle None from questionary
            email = ""

    return {
        "registry": registry,
        "username": username,
        "password": password,
        "email": email,
    }


def sync_image_pull_secrets(
    manifest_obj: AgentManifest,
    found_dockerconfigjson_secrets: list[dict],
    values_data: dict[str, Any],
    cluster: str,
    namespace: str,
    interactive: bool,
    changes: dict[str, list[str]],
) -> None:
    """Sync image pull secrets between manifest, cluster, and values file"""
    console.print(
        f"[bold]Syncing image pull secrets to cluster: {cluster} namespace: {namespace}[/bold]"
    )

    # Get the secrets of type KUBERNETES_SECRET_TYPE_DOCKERCONFIGJSON
    cluster_dockerconfigjson_secret_names = {
        secret["name"] for secret in found_dockerconfigjson_secrets
    }

    # Get the secrets from the manifest
    deployment_config: DeploymentConfig = manifest_obj.deployment
    manifest_image_pull_secrets: list[ImagePullSecretConfig] = (
        deployment_config.imagePullSecrets or []
    )

    if not manifest_image_pull_secrets:
        logger.info("No image pull secrets found in manifest")
        return

    # Get image pull secrets from values data
    image_pull_values = values_data

    # Process each required image pull secret
    for pull_secret in manifest_image_pull_secrets:
        secret_name = pull_secret.name
        current_secret_data = get_secret_data(secret_name, namespace, cluster)

        # Get new values
        new_registry = ""
        new_username = ""
        new_password = ""
        new_email = ""

        if secret_name in image_pull_values:
            # Get values from values file
            secret_config = image_pull_values[secret_name]
            new_registry = secret_config.get("registry", "")
            new_username = secret_config.get("username", "")
            new_password = secret_config.get("password", "")
            new_email = secret_config.get("email", "")

            if not new_registry or not new_username or not new_password:
                raise RuntimeError(
                    f"Incomplete image pull secret configuration for '{secret_name}'. "
                    f"Required: registry, username, password. Optional: email"
                )
        elif interactive:
            # Get values interactively
            if secret_name in cluster_dockerconfigjson_secret_names:
                console.print(
                    f"[blue]Image pull secret '{secret_name}' already exists[/blue]"
                )
                update_choice = questionary.select(
                    "What would you like to do?",
                    choices=["Keep current credentials", "Update with new credentials"],
                ).ask()
                update_choice = handle_questionary_cancellation(
                    update_choice, "image pull secret update choice"
                )

                if update_choice == "Keep current credentials":
                    continue  # Skip this secret

            console.print(
                f"[yellow]Image pull secret '{secret_name}' needs configuration[/yellow]"
            )
            creds = interactive_image_pull_secret_input(secret_name)
            new_registry = creds["registry"]
            new_username = creds["username"]
            new_password = creds["password"]
            new_email = creds["email"]
        else:
            raise RuntimeError(
                f"No configuration provided for image pull secret '{secret_name}'. "
                f"Provide values file or use interactive mode."
            )

        # Check if update is needed
        secret_needs_update = False
        action = ""

        if secret_name not in cluster_dockerconfigjson_secret_names:
            # Secret doesn't exist, needs creation
            secret_needs_update = True
            action = "create"
        else:
            # Secret exists, check if values changed
            current_dockerconfig = current_secret_data.get(".dockerconfigjson", {})
            current_auths = parse_dockerconfigjson_data(current_dockerconfig)
            if credentials_changed(
                current_auths, new_registry, new_username, new_password, new_email
            ):
                secret_needs_update = True
                action = "update"
            else:
                changes["noop"].append(
                    f"Secret '{secret_name}' key '{secret_name}' is up to date"
                )

        # Only perform action if update is needed
        if secret_needs_update:
            dockerconfig_string = create_dockerconfigjson_string(
                new_registry, new_username, new_password, new_email
            )
            secret_data = {".dockerconfigjson": dockerconfig_string}

            if action == "create":
                changes[action].append(
                    f"Create image pull secret '{secret_name}' for registry '{new_registry}'"
                )
                create_image_pull_secret_with_data(
                    secret_name, secret_data, namespace, cluster
                )
            elif action == "update":
                changes[action].append(
                    f"Update image pull secret '{secret_name}' (credentials changed)"
                )
                update_image_pull_secret_with_data(
                    secret_name, secret_data, namespace, cluster
                )


def print_changes_summary(change_type: str, changes: dict[str, list[str]]) -> None:
    # Show summary
    console.print(f"\n[bold]Sync Summary for {change_type}:[/bold]")
    if changes["create"]:
        console.print("[green]Created:[/green]")
        for change in changes["create"]:
            console.print(f"  ✓ {change}")

    if changes["update"]:
        console.print("[yellow]Updated:[/yellow]")
        for change in changes["update"]:
            console.print(f"  ⚠ {change}")

    if changes["noop"]:
        console.print("[yellow]No changes:[/yellow]")
        for change in changes["noop"]:
            console.print(f"  ✓ {change}")
        del changes["noop"]

    if not any(changes.values()):
        console.print(
            f"[green]✓ All secrets are already in sync for {change_type}[/green]"
        )

    console.print("")


def sync_secrets(
    manifest_obj: AgentManifest,
    cluster: str,
    namespace: str,
    interactive: bool,
    values_path: str | None,
) -> None:
    """Sync secrets between manifest, cluster, and values file"""
    logger.info(f"Syncing secrets to cluster: {cluster} namespace: {namespace}")

    # Load values from file if provided
    values_data = {}
    if values_path:
        try:
            # TODO: Convert this to a pydantic model to validate the values file
            values_data = load_values_file(values_path)
            console.print(f"[green]Loaded values from {values_path}[/green]")
        except Exception as e:
            console.print(f"[red]Error loading values file: {e}[/red]")
            raise

    # Get the secrets from the cluster using the specified namespace and cluster context
    cluster_secrets_by_type = get_kubernetes_secrets_by_type(
        namespace=namespace, context=cluster
    )

    # Track changes for summary
    changes = {"create": [], "update": [], "noop": []}

    sync_user_defined_secrets(
        manifest_obj,
        cluster_secrets_by_type[KUBERNETES_SECRET_TYPE_OPAQUE],
        values_data.get(
            KUBERNETES_SECRET_TO_MANIFEST_KEY[KUBERNETES_SECRET_TYPE_OPAQUE], {}
        ),
        cluster,
        namespace,
        interactive,
        changes,
    )

    print_changes_summary("User Defined Secrets", changes)

    # Track changes for summary
    changes = {"create": [], "update": [], "noop": []}

    sync_image_pull_secrets(
        manifest_obj,
        cluster_secrets_by_type[KUBERNETES_SECRET_TYPE_DOCKERCONFIGJSON],
        values_data.get(
            KUBERNETES_SECRET_TO_MANIFEST_KEY[KUBERNETES_SECRET_TYPE_DOCKERCONFIGJSON],
            {},
        ),
        cluster,
        namespace,
        interactive,
        changes,
    )

    print_changes_summary("Image Pull Secrets", changes)

    console.print(
        f"\n[green]Secret sync completed for cluster '{cluster}' namespace '{namespace}'[/green]"
    )
