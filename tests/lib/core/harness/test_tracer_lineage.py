"""SpanTracer stamps registered data-source refs onto tool spans (SGP-6513)."""

import pytest

from agentex.lib.core.harness.types import OpenSpan, CloseSpan
from agentex.lib.core.harness.tracer import SpanTracer
from agentex.lib.core.tracing.lineage import (
    LINEAGE_REFS_KEY,
    DataSourceRef,
    clear_tool_sources,
    register_tool_sources,
)

from ._fakes import FakeTracing


@pytest.fixture(autouse=True)
def _clean_registry():
    clear_tool_sources()
    yield
    clear_tool_sources()


@pytest.mark.asyncio
async def test_tool_open_span_carries_registered_refs():
    register_tool_sources(
        "query_guidance",
        refs=[DataSourceRef("databricks://ey-tax", "guidance.rulings")],
        resolver=lambda args: [DataSourceRef("elasticsearch://ey", args["index"])],
    )
    fake = FakeTracing()
    tracer = SpanTracer(trace_id="t1", parent_span_id="p1", tracing=fake)

    await tracer.handle(OpenSpan(key="c1", kind="tool", name="query_guidance", input={"index": "filings"}))
    await tracer.handle(CloseSpan(key="c1", output={"ok": True}, is_complete=True))

    (span,) = fake.ended_spans
    namespaces = {ref["namespace"] for ref in span.data[LINEAGE_REFS_KEY]}
    assert namespaces == {"databricks://ey-tax", "elasticsearch://ey"}


@pytest.mark.asyncio
async def test_unregistered_tool_and_reasoning_spans_carry_no_refs():
    fake = FakeTracing()
    tracer = SpanTracer(trace_id="t1", parent_span_id=None, tracing=fake)

    await tracer.handle(OpenSpan(key="c1", kind="tool", name="unregistered", input={}))
    await tracer.handle(CloseSpan(key="c1", output=None, is_complete=True))
    await tracer.handle(OpenSpan(key="reasoning:0", kind="reasoning", name="reasoning", input={}))
    await tracer.handle(CloseSpan(key="reasoning:0", output="thought", is_complete=True))

    for span in fake.ended_spans:
        assert not (isinstance(span.data, dict) and LINEAGE_REFS_KEY in span.data)
