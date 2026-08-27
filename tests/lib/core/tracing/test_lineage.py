"""Unit tests for the data-source ref module (sgp.lineage.refs capture)."""

import json

import pytest
from pydantic import ValidationError

from agentex.lib.core.tracing.lineage import (
    LINEAGE_REFS_KEY,
    DataSourceRef,
    record,
    data_sources,
    resolve_refs,
    clear_tool_sources,
    merge_refs_into_data,
    register_tool_sources,
    resolve_refs_from_items,
)


@pytest.fixture(autouse=True)
def _clean_registry():
    clear_tool_sources()
    yield
    clear_tool_sources()


ES_REF = DataSourceRef("elasticsearch://ey-embryonic", "companies_v3")
DBX_REF = DataSourceRef("databricks://ey-tax", "guidance.rulings", role="input")


class TestDataSourceRef:
    def test_positional_construction(self):
        ref = DataSourceRef("s3://bucket", "key", version="v1", role="output")
        assert ref.namespace == "s3://bucket"
        assert ref.name == "key"
        assert ref.version == "v1"
        assert ref.role == "output"

    def test_non_uri_namespace_rejected(self):
        with pytest.raises(ValidationError):
            DataSourceRef("not-a-uri", "name")

    def test_underscore_host_rejected(self):
        with pytest.raises(ValidationError):
            DataSourceRef("mcp://ey_tax_server", "competitive-edge")

    def test_host_with_path_segment_allowed(self):
        DataSourceRef("confluence://ey-tax/TAX", "page-123")

    def test_empty_name_rejected(self):
        with pytest.raises(ValidationError):
            DataSourceRef("s3://bucket", "")

    def test_bad_role_rejected(self):
        with pytest.raises(ValidationError):
            DataSourceRef("s3://bucket", "key", role="sideways")


class TestRegistryAndResolve:
    def test_unregistered_tool_resolves_empty(self):
        assert resolve_refs("unknown_tool", {}) == []

    def test_static_refs(self):
        register_tool_sources("search", refs=[ES_REF])
        refs = resolve_refs("search", {"q": "acme"})
        assert refs == [{"namespace": "elasticsearch://ey-embryonic", "name": "companies_v3", "role": "input"}]

    def test_resolver_refs_combined_with_static(self):
        register_tool_sources(
            "query_table",
            refs=[ES_REF],
            resolver=lambda args: [DataSourceRef("databricks://ey-tax", args["table"])],
        )
        refs = resolve_refs("query_table", {"table": "guidance.rulings"})
        assert {r["namespace"] for r in refs} == {"elasticsearch://ey-embryonic", "databricks://ey-tax"}

    def test_resolver_failure_keeps_static_refs(self):
        register_tool_sources("flaky", refs=[ES_REF], resolver=lambda args: args["missing"])
        refs = resolve_refs("flaky", {})
        assert len(refs) == 1

    def test_reregistration_replaces(self):
        register_tool_sources("search", refs=[ES_REF])
        register_tool_sources("search", refs=[DBX_REF])
        assert resolve_refs("search", {})[0]["namespace"] == "databricks://ey-tax"

    def test_dedupe(self):
        register_tool_sources("search", refs=[ES_REF, ES_REF])
        assert len(resolve_refs("search", {})) == 1


class TestDecorator:
    def test_registers_by_function_name(self):
        @data_sources(ES_REF)
        def search_companies(q: str) -> str:
            return q

        assert search_companies("x") == "x"
        assert resolve_refs("search_companies", {}) != []

    def test_registers_by_name_attribute(self):
        class FakeFunctionTool:
            name = "mcp_search"

        data_sources(DBX_REF)(FakeFunctionTool())
        assert resolve_refs("mcp_search", {}) != []


class TestResolveFromItems:
    def test_matches_function_call_items_and_parses_string_arguments(self):
        register_tool_sources(
            "query_table",
            resolver=lambda args: [DataSourceRef("databricks://ey-tax", args["table"])],
        )
        items = [
            {"type": "message", "content": []},
            {"type": "function_call", "name": "query_table", "arguments": json.dumps({"table": "t1"})},
            {"type": "function_call", "name": "unregistered", "arguments": "{}"},
            "not-a-dict",
        ]
        refs = resolve_refs_from_items(items)
        assert refs == [{"namespace": "databricks://ey-tax", "name": "t1", "role": "input"}]

    def test_malformed_arguments_fall_back_to_static(self):
        register_tool_sources("search", refs=[ES_REF])
        items = [{"type": "function_call", "name": "search", "arguments": "{not json"}]
        assert len(resolve_refs_from_items(items)) == 1


class TestRecordAndMerge:
    def test_record_on_none_span_is_noop(self):
        record(None, [ES_REF])

    def test_record_merges_into_span_data(self):
        class Span:
            data = {"__span_type__": "CUSTOM"}

        span = Span()
        record(span, [ES_REF])
        assert span.data["__span_type__"] == "CUSTOM"
        assert span.data[LINEAGE_REFS_KEY][0]["name"] == "companies_v3"

    def test_merge_dedupes_against_existing(self):
        data = merge_refs_into_data(None, [ES_REF.model_dump(exclude_none=True)])
        data = merge_refs_into_data(data, [ES_REF.model_dump(exclude_none=True)])
        assert len(data[LINEAGE_REFS_KEY]) == 1
