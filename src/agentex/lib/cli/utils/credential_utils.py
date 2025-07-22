import subprocess

from rich.console import Console
from rich.prompt import Confirm, Prompt

from agentex.lib.types.credentials import CredentialMapping

console = Console()


def check_secret_exists(secret_name: str, namespace: str) -> bool:
    """Check if a Kubernetes secret exists in the given namespace."""
    try:
        result = subprocess.run(
            ["kubectl", "get", "secret", secret_name, "-n", namespace],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode == 0
    except Exception:
        return False


def create_env_var_secret(credential: CredentialMapping, namespace: str) -> bool:
    """Create a generic secret for environment variable credentials."""
    console.print(
        f"[yellow]Secret '{credential.secret_name}' not found in namespace '{namespace}'[/yellow]"
    )

    if not Confirm.ask(
        f"Would you like to create the secret '{credential.secret_name}'?"
    ):
        return False

    # Prompt for the secret value
    secret_value = Prompt.ask(
        f"Enter the value for '{credential.secret_key}'", password=True
    )

    try:
        # Create the secret using kubectl
        subprocess.run(
            [
                "kubectl",
                "create",
                "secret",
                "generic",
                credential.secret_name,
                f"--from-literal={credential.secret_key}={secret_value}",
                "-n",
                namespace,
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        console.print(
            f"[green]✓ Created secret '{credential.secret_name}' in namespace '{namespace}'[/green]"
        )
        return True

    except subprocess.CalledProcessError as e:
        console.print(f"[red]✗ Failed to create secret: {e.stderr}[/red]")
        return False


# def create_image_pull_secret(credential: ImagePullCredential, namespace: str) -> bool:
#     """Create an image pull secret with interactive prompts."""
#     console.print(f"[yellow]Image pull secret '{credential.secret_name}' not found in namespace '{namespace}'[/yellow]")

#     if not Confirm.ask(f"Would you like to create the image pull secret '{credential.secret_name}'?"):
#         return False

#     # Prompt for registry details
#     registry_server = Prompt.ask("Docker registry server (e.g., docker.io, gcr.io)")
#     username = Prompt.ask("Username")
#     password = Prompt.ask("Password", password=True)
#     email = Prompt.ask("Email (optional)", default="")

#     try:
#         # Create the image pull secret using kubectl
#         cmd = [
#             "kubectl", "create", "secret", "docker-registry",
#             credential.secret_name,
#             f"--docker-server={registry_server}",
#             f"--docker-username={username}",
#             f"--docker-password={password}",
#             "-n", namespace
#         ]

#         if email:
#             cmd.append(f"--docker-email={email}")

#         result = subprocess.run(cmd, capture_output=True, text=True, check=True)

#         console.print(f"[green]✓ Created image pull secret '{credential.secret_name}' in namespace '{namespace}'[/green]")
#         return True

#     except subprocess.CalledProcessError as e:
#         console.print(f"[red]✗ Failed to create image pull secret: {e.stderr}[/red]")
#         return False
