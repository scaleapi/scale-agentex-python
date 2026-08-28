# Lineage provenance on agent traces

A sync agent (same harness surface as `050_openai_agents`) whose spans carry
the provenance that SGP Lineage derives graph edges from: which data sources
each tool call read, and which agent build produced the trace.

## What this demonstrates

Two span-metadata conventions, both capture-only — nothing here emits to the
lineage service; edges are derived later from materialized traces
([SGP-6513 convention spec](https://github.com/scaleapi/scaleapi/blob/master/packages/sgp-lineage/docs/specs/2026-07-22-sgp-6513-trace-data-source-ref-convention.md)):

- **`sgp.lineage.refs`** — each tool declares the data sources it reads, via
  the three capture forms in `agentex.lib.adk.lineage`:

  ```python
  @function_tool
  @data_sources(DataSourceRef("elasticsearch://research-cluster", "filings-v1"))
  def search_filings(query: str) -> str: ...          # static refs

  @function_tool
  @data_sources(resolver=_kpi_refs)
  def read_kpi(table: str) -> str: ...                # refs derived from arguments

  lineage.register_tool_sources(                      # tools you don't own (MCP)
      "company_profile", [DataSourceRef("mcp://research-mcp", "company-profiles")]
  )
  ```

  The harness resolves these on every tool span and merges them into
  `span.data["sgp.lineage.refs"]`.

- **`__agent_version__`** — the SGP tracing processor stamps the
  `AGENT_VERSION` env var onto every span. The Dockerfile sets it from a
  build arg; real deployments pass the image tag or git SHA. For
  `agentex agents run`, export it or put it in this directory's `.env`.

Ref namespaces must use the canonical URI forms from the lineage identifier
conventions (`packages/sgp-lineage/docs/event-contract.md` in `scaleapi`);
malformed namespaces raise at import time.

## Run it

```bash
agentex agents run --manifest manifest.yaml
```

Ask it to "research ACME Corp" — the instructions route through all three
tools. With `SGP_API_KEY` / `SGP_ACCOUNT_ID` / `SGP_CLIENT_BASE_URL` set, the
resulting trace's tool spans show `sgp.lineage.refs` (and every span
`__agent_version__`) in their metadata, filterable in the SGP traces UI and
spans-search `extra_metadata` DSL.

## Test it

The offline test verifies all three capture forms resolve without a server or
API key:

```bash
pytest tests/test_agent.py -v
```
