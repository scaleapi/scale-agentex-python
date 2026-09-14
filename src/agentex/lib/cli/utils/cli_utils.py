from __future__ import annotations

import typer
from rich.console import Console

console = Console()

# asyncio's StreamReader defaults to 64 KiB, and a single log line above that makes
# readline() raise. Agents legitimately emit large lines (serialized charts, payloads
# echoed back by validation errors), so give the reader room before it has to drop one.
#
# Lives here rather than beside its users so that both the normal spawns in
# cli/handlers/run_handlers.py and the debug spawns in cli/debug/debug_handlers.py can
# import it: run_handlers imports cli.debug, so the constant cannot live in either one.
# Keep the two in step. A subprocess left on the asyncio default overruns far more
# easily, and enough consecutive overruns exhaust the reader's retry bound and stop it
# draining, which is the deadlock the bound is there to avoid.
SUBPROCESS_STREAM_LIMIT = 8 * 1024 * 1024


def handle_questionary_cancellation(
    result: str | None, operation: str = "operation"
) -> str:
    """Handle questionary cancellation by checking for None and exiting gracefully"""
    if result is None:
        console.print(f"[yellow]{operation.capitalize()} cancelled by user[/yellow]")
        raise typer.Exit(0)
    return result
