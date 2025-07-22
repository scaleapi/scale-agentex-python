import typer
from rich.console import Console

console = Console()


def handle_questionary_cancellation(
    result: str | None, operation: str = "operation"
) -> str:
    """Handle questionary cancellation by checking for None and exiting gracefully"""
    if result is None:
        console.print(f"[yellow]{operation.capitalize()} cancelled by user[/yellow]")
        raise typer.Exit(0)
    return result
