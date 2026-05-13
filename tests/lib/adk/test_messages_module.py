"""Tests for MessagesModule's workflow.now() auto-injection on create/create_batch.

Verifies that inside a Temporal workflow context, MessagesModule.create and
create_batch default `created_at` to workflow.now(), threading it through both
the activity dispatch branch and the direct service-call branch. Outside a
workflow, created_at remains None and the server's wall clock applies.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

import agentex.lib.adk._modules.messages as _messages_mod
from agentex.types.task_message import TaskMessage
from agentex.types.text_content import TextContent
from agentex.lib.adk._modules.messages import MessagesModule
from agentex.lib.core.services.adk.messages import MessagesService

_FIXED_NOW = datetime(2026, 5, 13, 18, 30, 0, tzinfo=timezone.utc)


def _make_task_message() -> TaskMessage:
    return TaskMessage(
        id="m1",
        task_id="t1",
        content=TextContent(author="agent", content="hi", format="markdown"),
        streaming_status="DONE",
    )


def _make_module() -> tuple[AsyncMock, MessagesModule]:
    mock_service = AsyncMock(spec=MessagesService)
    module = MessagesModule(messages_service=mock_service)
    return mock_service, module


class TestMessagesModuleCreate:
    @pytest.mark.asyncio
    async def test_outside_workflow_does_not_inject_created_at(self) -> None:
        mock_service, module = _make_module()
        mock_service.create_message.return_value = _make_task_message()

        with patch.object(_messages_mod, "in_temporal_workflow", return_value=False):
            await module.create(
                task_id="t1",
                content=TextContent(author="user", content="hi", format="markdown"),
            )

        kwargs = mock_service.create_message.call_args.kwargs
        assert kwargs["created_at"] is None

    @pytest.mark.asyncio
    async def test_inside_workflow_auto_injects_workflow_now(self) -> None:
        mock_service, module = _make_module()
        mock_service.create_message.return_value = _make_task_message()

        # Stub the activity helper so we don't try to actually dispatch.
        # Capture the params object so we can assert created_at.
        captured: dict = {}

        async def fake_execute_activity(**call_kwargs):
            captured.update(call_kwargs)
            return _make_task_message()

        with patch.object(_messages_mod, "in_temporal_workflow", return_value=True), patch.object(
            _messages_mod, "workflow_now_if_in_workflow", return_value=_FIXED_NOW
        ), patch.object(
            _messages_mod.ActivityHelpers,
            "execute_activity",
            side_effect=fake_execute_activity,
        ):
            await module.create(
                task_id="t1",
                content=TextContent(author="user", content="hi", format="markdown"),
            )

        params = captured["request"]
        assert params.created_at == _FIXED_NOW

    @pytest.mark.asyncio
    async def test_caller_supplied_created_at_is_respected(self) -> None:
        mock_service, module = _make_module()
        mock_service.create_message.return_value = _make_task_message()
        caller_ts = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

        # Caller already supplied a timestamp: don't overwrite.
        with patch.object(_messages_mod, "in_temporal_workflow", return_value=False):
            await module.create(
                task_id="t1",
                content=TextContent(author="user", content="hi", format="markdown"),
                created_at=caller_ts,
            )

        kwargs = mock_service.create_message.call_args.kwargs
        assert kwargs["created_at"] == caller_ts


class TestMessagesModuleCreateBatch:
    @pytest.mark.asyncio
    async def test_inside_workflow_auto_injects_workflow_now(self) -> None:
        mock_service, module = _make_module()
        mock_service.create_messages_batch.return_value = [_make_task_message()]

        captured: dict = {}

        async def fake_execute_activity(**call_kwargs):
            captured.update(call_kwargs)
            return [_make_task_message()]

        with patch.object(_messages_mod, "in_temporal_workflow", return_value=True), patch.object(
            _messages_mod, "workflow_now_if_in_workflow", return_value=_FIXED_NOW
        ), patch.object(
            _messages_mod.ActivityHelpers,
            "execute_activity",
            side_effect=fake_execute_activity,
        ):
            await module.create_batch(
                task_id="t1",
                contents=[TextContent(author="user", content="hi", format="markdown")],
            )

        params = captured["request"]
        assert params.created_at == _FIXED_NOW
