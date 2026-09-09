"""Tool implementations for the lineage tutorial.

The bare functions live here so they're easy to unit-test; they're wrapped as
OpenAI Agents SDK ``function_tool``s — and annotated with data-source refs —
in ``project.agent``. Outputs are canned so the tutorial runs offline.
"""

from __future__ import annotations


def search_filings(query: str) -> str:
    """Search the filings index for documents matching a query."""
    return f'Top filing for "{query}": ACME Corp 10-K (2025) — revenue up 12%, filed 2026-02-14.'


def read_kpi(table: str) -> str:
    """Read a KPI summary row from a metrics table."""
    return f"{table}: latest value 4.2M, trailing 12-month growth 8%."


def company_profile(name: str) -> str:
    """Fetch a company profile (stands in for an MCP-server tool)."""
    return f"{name}: industrial supplier, HQ Albuquerque, 1,200 employees, founded 1952."
