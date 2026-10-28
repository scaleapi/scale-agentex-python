"""The tool result the OpenAI hooks record on a tool span.

The failure checks decode the recorded text as JSON, so an object result has to be written as JSON.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any, override
from datetime import UTC, datetime

import pytest

import agentex.lib.core.temporal.plugins.openai_agents.hooks.hooks as hooks_module
from agentex.types.span import Span
from agentex.lib.core.temporal.plugins.openai_agents.hooks.hooks import TemporalStreamingHooks

pytestmark = pytest.mark.asyncio


class _FakeTracing:
    def __init__(self) -> None:
        self.ended: list[Span] = []

    async def start_span(
        self, *, trace_id: str, name: str, input: Any = None, parent_id: str | None = None, **_: Any
    ) -> Span:
        return Span(
            id="span-1", name=name, start_time=datetime.now(UTC), trace_id=trace_id, parent_id=parent_id, input=input
        )

    async def end_span(self, *, trace_id: str, span: Span, **_: Any) -> Span:
        self.ended.append(span)
        return span


@pytest.fixture
def tracing(monkeypatch: pytest.MonkeyPatch) -> _FakeTracing:
    fake = _FakeTracing()
    monkeypatch.setattr(hooks_module, "_get_adk", lambda: SimpleNamespace(tracing=fake))
    return fake


async def _recorded_output(tracing: _FakeTracing, result: Any) -> Any:
    hooks = TemporalStreamingHooks(task_id="task-1", trace_id="trace-1")
    await hooks._maybe_start_tool_span("call-1", "lookup", {})
    await hooks._maybe_end_tool_span("call-1", result)
    (span,) = tracing.ended
    return span.output


async def test_object_result_is_recorded_as_json(tracing: _FakeTracing) -> None:
    result = {"city": "Paris", "temps": [12, 15], "raining": False, "note": None}
    output = await _recorded_output(tracing, result)
    assert output == {"result": '{"city": "Paris", "temps": [12, 15], "raining": false, "note": null}'}
    assert json.loads(output["result"]) == result


async def test_list_result_is_recorded_as_json(tracing: _FakeTracing) -> None:
    output = await _recorded_output(tracing, [1, "two", {"three": 3}])
    assert output == {"result": '[1, "two", {"three": 3}]'}


@pytest.mark.parametrize(("result", "text"), [(None, "null"), (True, "true"), (3, "3"), (1.5, "1.5")])
async def test_scalar_result_is_recorded_as_json(tracing: _FakeTracing, result: Any, text: str) -> None:
    assert await _recorded_output(tracing, result) == {"result": text}


@pytest.mark.parametrize("text", ["plain text", '{"already": "json"}', ""])
async def test_string_result_is_recorded_as_it_is(tracing: _FakeTracing, text: str) -> None:
    assert await _recorded_output(tracing, text) == {"result": text}


class _Opaque:
    @override
    def __str__(self) -> str:
        return "opaque result"


def _circular() -> dict[str, Any]:
    result: dict[str, Any] = {}
    result["self"] = result
    return result


@pytest.mark.parametrize(
    ("result", "text"), [(_Opaque(), "opaque result"), (_circular(), "{'self': {...}}")], ids=["object", "circular"]
)
async def test_result_that_cannot_be_serialized_falls_back_to_str(
    tracing: _FakeTracing, result: Any, text: str
) -> None:
    assert await _recorded_output(tracing, result) == {"result": text}


async def test_json_result_is_capped(tracing: _FakeTracing) -> None:
    result = {"rows": ["x" * 100] * 50}
    output = await _recorded_output(tracing, result)
    assert len(output["result"]) == 2000
    assert json.dumps(result).startswith(output["result"])


async def test_string_result_is_capped(tracing: _FakeTracing) -> None:
    assert await _recorded_output(tracing, "y" * 5000) == {"result": "y" * 2000}
