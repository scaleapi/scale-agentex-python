"""Unit tests for hosted/server-side tool rendering helpers.

These cover the pure extraction helpers used by TemporalStreamingModel to surface
Responses-API hosted tools (web_search, file_search, code_interpreter, mcp, ...)
as ToolRequest/ToolResponse pairs. They never become function_call items, so the
streaming loop must render them explicitly.
"""

from __future__ import annotations

from types import SimpleNamespace

from agentex.lib.core.temporal.plugins.openai_agents.models.temporal_streaming_model import (
    _HOSTED_TOOL_TYPES,
    _coerce_args,
    _hosted_tool_result,
    _hosted_tool_request,
)


def test_hosted_tool_types_membership():
    for t in ("web_search_call", "file_search_call", "code_interpreter_call",
              "image_generation_call", "mcp_call"):
        assert t in _HOSTED_TOOL_TYPES
    assert "function_call" not in _HOSTED_TOOL_TYPES


def test_coerce_args_variants():
    assert _coerce_args(None) == {}
    assert _coerce_args({"a": 1}) == {"a": 1}
    assert _coerce_args('{"a": 1}') == {"a": 1}
    assert _coerce_args("[1, 2]") == {"value": [1, 2]}
    assert _coerce_args("not json") == {"raw": "not json"}


def test_hosted_tool_request_web_search():
    item = SimpleNamespace(type="web_search_call", id="ws_1",
                           action={"query": "agentex"})
    call_id, name, args = _hosted_tool_request(item)
    assert call_id == "ws_1"
    assert name == "web_search"  # "_call" stripped
    assert args == {"query": "agentex"}


def test_hosted_tool_request_mcp_uses_server_label():
    item = SimpleNamespace(type="mcp_call", id="m_1", name="search",
                           server_label="linear", arguments='{"q": "x"}')
    call_id, name, args = _hosted_tool_request(item)
    assert call_id == "m_1"
    assert name == "linear.search"
    assert args == {"q": "x"}


def test_hosted_tool_request_file_search_queries():
    item = SimpleNamespace(type="file_search_call", id="fs_1",
                           queries=["q1", "q2"])
    _, name, args = _hosted_tool_request(item)
    assert name == "file_search"
    assert args == {"queries": ["q1", "q2"]}


def test_hosted_tool_request_falls_back_to_generated_id():
    item = SimpleNamespace(type="code_interpreter_call", code="print(1)")
    call_id, name, args = _hosted_tool_request(item)
    assert call_id.startswith("hosted_")
    assert name == "code_interpreter"
    assert args == {"code": "print(1)"}


def test_hosted_tool_result_mcp_error_and_output():
    err_item = SimpleNamespace(type="mcp_call", error="boom")
    assert "boom" in _hosted_tool_result(err_item)
    ok_item = SimpleNamespace(type="mcp_call", error=None, output="done")
    assert _hosted_tool_result(ok_item) == "done"


def test_hosted_tool_result_falls_back_to_status():
    item = SimpleNamespace(type="web_search_call", status="completed")
    assert _hosted_tool_result(item) == "completed"
