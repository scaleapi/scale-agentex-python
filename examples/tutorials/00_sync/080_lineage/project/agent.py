"""OpenAI Agents SDK agent whose tool calls carry lineage data-source refs.

Each tool declares the data sources it reads via one of the three capture
forms in ``agentex.lib.adk.lineage`` (see README.md); the harness resolves
them on every tool span into ``span.data["sgp.lineage.refs"]``. Capture only —
nothing here emits to the lineage service.
"""

from __future__ import annotations

from agents import Agent, function_tool, set_tracing_disabled

from project import tools
from agentex.lib.adk import DataSourceRef, lineage, data_sources

# Disable the openai-agents SDK's native tracer so it doesn't ship traces to
# api.openai.com (the key may be a gateway/proxy key). Agentex tracing still
# runs via the harness + tracing manager configured in acp.py.
set_tracing_disabled(True)

MODEL_NAME = "gpt-4o"
INSTRUCTIONS = """You are a market-research assistant with access to tools.

Guidelines:
- To research a company, use all three tools: search_filings, read_kpi
  (table="revenue"), and company_profile.
- Be concise, and always report the real tool output back to the user.
"""


@function_tool
@data_sources(DataSourceRef("elasticsearch://research-cluster", "filings-v1"))
def search_filings(query: str) -> str:
    """Search the filings index for documents matching a query."""
    return tools.search_filings(query)


def _kpi_refs(args: dict) -> list[DataSourceRef]:
    table = args.get("table")
    if not table:
        return []
    return [DataSourceRef("databricks://demo-workspace.cloud.databricks.com", f"main.kpi.{table}")]


@function_tool
@data_sources(resolver=_kpi_refs)
def read_kpi(table: str) -> str:
    """Read a KPI summary row from a metrics table."""
    return tools.read_kpi(table)


@function_tool
def company_profile(name: str) -> str:
    """Fetch a company profile."""
    return tools.company_profile(name)


# company_profile stands in for a tool this codebase doesn't own (e.g. an MCP
# server's tool), so its refs are registered by name instead of decorating it.
lineage.register_tool_sources(
    "company_profile",
    [DataSourceRef("mcp://research-mcp", "company-profiles")],
)


def create_agent() -> Agent:
    """Build and return the agent with the three ref-carrying tools."""
    return Agent(
        name="Lineage Research Assistant",
        model=MODEL_NAME,
        instructions=INSTRUCTIONS,
        tools=[search_filings, read_kpi, company_profile],
    )
