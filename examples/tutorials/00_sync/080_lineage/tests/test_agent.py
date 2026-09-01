"""Offline test for the lineage tutorial.

This test does NOT require a running Agentex server or an OpenAI API key. It
verifies the tutorial's lineage wiring: each of the three capture forms in
``project.agent`` (static decorator, resolver, name-keyed registry) resolves
to the declared data-source refs under the tool name the harness sees.

To run: ``pytest tests/test_agent.py -v``
"""

from __future__ import annotations

import project.agent  # noqa: F401  — registers the tutorial's tool refs on import

from agentex.lib.adk import lineage


def test_static_decorator_refs_resolve_under_function_tool_name():
    refs = lineage.resolve_refs("search_filings", {"query": "acme"})
    assert refs == [{"namespace": "elasticsearch://research-cluster", "name": "filings-v1", "role": "input"}]


def test_resolver_derives_ref_from_tool_arguments():
    refs = lineage.resolve_refs("read_kpi", {"table": "revenue"})
    assert refs == [
        {
            "namespace": "databricks://demo-workspace.cloud.databricks.com",
            "name": "main.kpi.revenue",
            "role": "input",
        }
    ]


def test_resolver_yields_nothing_without_the_argument():
    assert lineage.resolve_refs("read_kpi", {}) == []


def test_registry_covers_the_unowned_tool():
    refs = lineage.resolve_refs("company_profile", {"name": "ACME"})
    assert refs == [{"namespace": "mcp://research-mcp", "name": "company-profiles", "role": "input"}]


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
