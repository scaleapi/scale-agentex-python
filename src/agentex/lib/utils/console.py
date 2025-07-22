from rich import box
from rich.console import Console
from rich.table import Table

console = Console()


def print_section(name: str, contents: list[str], subtitle: str | None = None):
    console.print()
    table = Table(box=box.SQUARE, caption=subtitle, show_header=False, expand=True)
    table.title = name
    table.add_column(name, style="dim", width=12)
    table.add_row(*contents)
    console.print(table)
