"""Validate that ADK requests stay valid against a window of supported server
OpenAPI contracts (server_specs/); see server_specs/manifest.json for the window."""

from __future__ import annotations

import json
from typing import Any
from pathlib import Path
from unittest.mock import Mock

import yaml
import httpx
import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from agentex import AsyncAgentex
from agentex.lib.core.services.adk.state import StateService

_SPEC_DIR = Path(__file__).parent / "server_specs"
_BASE_URL = "http://127.0.0.1:4010"
_STATE_RESPONSE = {
    "id": "s1",
    "agent_id": "a1",
    "task_id": "t1",
    "state": {"k": "v"},
    "created_at": "2026-05-13T18:30:00Z",
}


def _window() -> list[dict[str, Any]]:
    manifest = json.loads((_SPEC_DIR / "manifest.json").read_text())
    return [
        {"label": e["label"], "spec": yaml.safe_load((_SPEC_DIR / e["file"]).read_text())} for e in manifest["specs"]
    ]


def _mock_span():
    span = Mock()
    span.output = None

    async def __aenter__(_self):
        return span

    async def __aexit__(_self, *args):
        return None

    span.__aenter__ = __aenter__
    span.__aexit__ = __aexit__
    return span


def _state_service(client: AsyncAgentex) -> StateService:
    tracer = Mock()
    trace = Mock()
    trace.span.return_value = _mock_span()
    tracer.trace.return_value = trace
    return StateService(agentex_client=client, tracer=tracer)


async def _drive_update(svc: StateService) -> None:
    await svc.update_state(state_id="s1", task_id="t1", agent_id="a1", state={"k": "v"})


async def _drive_create(svc: StateService) -> None:
    await svc.create_state(task_id="t1", agent_id="a1", state={"k": "v"})


# Each ADK operation: how to drive it, the request it emits, and the server-spec
# operation (path template + method) whose requestBody its body must satisfy.
_OPERATIONS = [
    {
        "label": "states.update",
        "http_method": "PUT",
        "url": f"{_BASE_URL}/states/s1",
        "spec_path": "/states/{state_id}",
        "spec_method": "put",
        "drive": _drive_update,
    },
    {
        "label": "states.create",
        "http_method": "POST",
        "url": f"{_BASE_URL}/states",
        "spec_path": "/states",
        "spec_method": "post",
        "drive": _drive_create,
    },
]

_WINDOW = _window()


def _deref(schema: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    ref = schema.get("$ref")
    if not ref or not ref.startswith("#/"):
        return schema
    node: Any = spec
    for part in ref[2:].split("/"):
        node = node[part]
    return node


def _request_body_schema(spec: dict[str, Any], path: str, method: str) -> dict[str, Any]:
    schema = spec["paths"][path][method]["requestBody"]["content"]["application/json"]["schema"]
    return _deref(schema, spec)


@pytest.mark.parametrize("entry", _WINDOW, ids=lambda e: e["label"])
@pytest.mark.parametrize("op", _OPERATIONS, ids=lambda o: o["label"])
async def test_adk_request_validates_against_server_spec(
    op: dict[str, Any], entry: dict[str, Any], respx_mock: Any
) -> None:
    route = respx_mock.route(method=op["http_method"], url=op["url"]).mock(
        return_value=httpx.Response(200, json=_STATE_RESPONSE)
    )
    async with AsyncAgentex(base_url=_BASE_URL, api_key="test") as client:
        await op["drive"](_state_service(client))

    assert route.called, f"{op['label']} did not hit {op['url']}"
    body = json.loads(route.calls.last.request.content)

    spec = entry["spec"]
    registry = Registry().with_resource(uri="", resource=Resource(contents=spec, specification=DRAFT202012))
    schema = _request_body_schema(spec, op["spec_path"], op["spec_method"])
    errors = sorted(Draft202012Validator(schema, registry=registry).iter_errors(body), key=str)
    assert not errors, f"{op['label']} request {body} violates server contract '{entry['label']}': " + "; ".join(
        e.message for e in errors
    )
