"""Forwarded request headers must stay out of the string form of ACP params.

``BaseACPServer`` copies inbound ``x-*`` headers (which can carry end-user
credentials) into ``params.request``. Agent code commonly logs ``f"{params}"``,
so ``request`` is excluded from ``str()``/``repr()``, while handlers and the
Temporal signal payload (``model_dump()``) still receive it.
"""

from __future__ import annotations

import pytest

from agentex.types.task import Task
from agentex.types.agent import Agent
from agentex.types.event import Event
from agentex.protocol.acp import (
    SendEventParams,
    CancelTaskParams,
    CreateTaskParams,
    SendMessageParams,
    InterruptTaskParams,
)
from agentex.types.text_content import TextContent

CANARY = "canary-forwarded-header-value"
REQUEST = {"headers": {"x-user-oauth-credentials": CANARY}}

_agent = Agent(
    id="agent-1",
    name="agent",
    description="d",
    acp_type="async",
    created_at="2023-01-01T00:00:00Z",
    updated_at="2023-01-01T00:00:00Z",
)
_task = Task(id="task-1")
_content = TextContent(author="user", content="hi")
_event = Event(id="event-1", agent_id="agent-1", task_id="task-1", sequence_id=1, content=_content)

AnyParams = CreateTaskParams | SendMessageParams | SendEventParams | CancelTaskParams | InterruptTaskParams

PARAMS: list[AnyParams] = [
    CreateTaskParams(agent=_agent, task=_task, params={"k": "v"}, request=REQUEST),
    SendMessageParams(agent=_agent, task=_task, content=_content, stream=False, request=REQUEST),
    SendEventParams(agent=_agent, task=_task, event=_event, request=REQUEST),
    CancelTaskParams(agent=_agent, task=_task, request=REQUEST),
    InterruptTaskParams(agent=_agent, task=_task, request=REQUEST),
]


@pytest.mark.parametrize("params", PARAMS, ids=lambda p: type(p).__name__)
def test_header_values_absent_from_str_and_repr(params: AnyParams) -> None:
    assert CANARY not in str(params)
    assert CANARY not in repr(params)
    assert "task-1" in str(params)


@pytest.mark.parametrize("params", PARAMS, ids=lambda p: type(p).__name__)
def test_headers_still_reach_handlers_and_payloads(params: AnyParams) -> None:
    assert params.request == REQUEST
    dumped = params.model_dump()
    assert dumped["request"] == REQUEST
    assert CANARY in params.model_dump_json()
    # TemporalTaskService signals model_dump() and the workflow re-validates it.
    assert type(params).model_validate(dumped).request == REQUEST
